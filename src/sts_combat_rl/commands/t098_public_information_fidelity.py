"""Focused T098 public-information fidelity re-entry.

The native simulator owns every Battle transition and hidden-future sample.
This module restores explicit portable anchors, calls the native projection and
sampler APIs, validates their public-only results, and writes a compact report.
It does not construct or mutate hidden simulator mechanics in Python.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from sts_combat_rl.sim.assisted_source_generation import (
    restore_assisted_battle_start_record,
)
from sts_combat_rl.sim.battle_start_pool import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    record_from_manifest,
    restore_battle_start_record,
)
from sts_combat_rl.sim.t096_public_information_sampler import (
    T096SamplerError,
    canonical_json,
    canonical_sha256,
    compare_public_information,
    public_action_identities,
    validate_public_information_projection,
)

T098_TASK_ID = "T098"
T098_REPORT_SCHEMA_ID = "t098-public-information-fidelity-reentry-v1"
T098_WITNESS_SCHEMA_ID = "t098-public-information-runtime-witness-v1"
T098_PARTICLE_COUNT = 32
T098_NATIVE_COMMIT = "d309170198e21e57041a84dcfdbc255cdda4052e"
T098_NATIVE_AUDIT_SCHEMA_ID = "native-battle-visibility-audit-v1"
_T098_ALLOWED_DISTRIBUTIONS = frozenset(
    {NATURAL_DISTRIBUTION_KIND, ASSISTED_RUN_DISTRIBUTION_KIND}
)

_NATIVE_AUDIT_BOOLEAN_FIELDS = frozenset(
    {
        "headbutt_known_prefix",
        "native_snapshot_contract",
        "checkpoint_preserves_known_prefix",
        "sampler_preserves_known_prefix",
        "sampler_public_information_invariant",
        "sampler_private_remainder_diverse",
        "havoc_consumes_top_preserves_suffix",
        "rebound_establishes_known_top",
        "forethought_known_position_preserved",
        "subset_reveal_fails_closed",
        "subset_reveal_shuffle_stays_unsupported",
        "subset_reveal_sampler_fails_closed",
        "draw_knowledge_reason_typed",
        "frozen_eye_full_order",
        "frozen_eye_sampler_preserves_order",
        "runic_dome_hides_current_intent",
        "runic_dome_preserves_previous_move",
        "runic_dome_sanitizes_roll_misc",
        "runic_dome_hidden_counter_timing_invariant",
        "runic_dome_mixed_counter_sampler_fails_closed",
        "runic_dome_hides_louse_misc",
        "private_hidden_state_projection_invariant",
        "runic_dome_looter_public_counter_preserved",
        "runic_dome_looter_misc_fails_closed",
        "private_hidden_misc_sampler_supported",
        "runic_dome_retains_visible_power",
        "runic_dome_direct_misc_fail_closed",
    }
)


def validate_t098_native_visibility_audit(value: object) -> dict[str, Any]:
    """Validate the exact pinned native audit surface, fail closed."""

    if not isinstance(value, Mapping):
        raise T096SamplerError("T098 native visibility audit must be a mapping")
    audit = dict(value)
    expected = _NATIVE_AUDIT_BOOLEAN_FIELDS | {"schema_id"}
    if set(audit) != expected:
        raise T096SamplerError(
            "T098 native visibility audit keys mismatch; "
            f"missing={sorted(expected - set(audit))}, "
            f"unknown={sorted(set(audit) - expected)}"
        )
    if audit["schema_id"] != T098_NATIVE_AUDIT_SCHEMA_ID:
        raise T096SamplerError("T098 native visibility audit schema mismatch")
    for field in _NATIVE_AUDIT_BOOLEAN_FIELDS:
        if not isinstance(audit[field], bool):
            raise T096SamplerError(f"T098 native audit field {field} is not boolean")
    return audit


def load_portable_battle_start_record(
    stream: TextIO, *, record_index: int
) -> BattleStartCheckpointRecord:
    """Read one explicit record from a portable pool without loading the pool."""

    if isinstance(record_index, bool) or not isinstance(record_index, int):
        raise TypeError("T098 record index must be an integer")
    if record_index < 0:
        raise ValueError("T098 record index must be non-negative")
    metadata = json.loads(stream.readline())
    if not isinstance(metadata, Mapping) or metadata.get("type") != "metadata":
        raise ValueError("T098 portable pool lacks its metadata row")
    for line_number, line in enumerate(stream, start=0):
        row = json.loads(line)
        if not isinstance(row, Mapping) or row.get("type") != "record":
            continue
        raw = row.get("record")
        if not isinstance(raw, Mapping):
            raise TypeError(f"T098 pool record {line_number} is malformed")
        current = raw.get("record_index")
        if current == record_index:
            return record_from_manifest(
                raw,
                label=f"T098 record {record_index}",
                allowed_distribution_kinds=_T098_ALLOWED_DISTRIBUTIONS,
                allow_assistance_history=True,
            )
        if isinstance(current, int) and current > record_index:
            break
    raise ValueError(f"T098 portable pool record {record_index} was not found")


def load_portable_battle_start_records(
    stream: TextIO, *, record_indices: Sequence[int]
) -> dict[int, BattleStartCheckpointRecord]:
    """Read several explicit records in one streaming pass."""

    wanted = set(record_indices)
    if (
        not wanted
        or len(wanted) != len(record_indices)
        or any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0
            for index in wanted
        )
    ):
        raise ValueError("T098 record indices must be unique non-negative integers")
    metadata = json.loads(stream.readline())
    if not isinstance(metadata, Mapping) or metadata.get("type") != "metadata":
        raise ValueError("T098 portable pool lacks its metadata row")
    found: dict[int, BattleStartCheckpointRecord] = {}
    for line_number, line in enumerate(stream, start=0):
        row = json.loads(line)
        if not isinstance(row, Mapping) or row.get("type") != "record":
            continue
        raw = row.get("record")
        if not isinstance(raw, Mapping):
            raise TypeError(f"T098 pool record {line_number} is malformed")
        current = raw.get("record_index")
        if current in wanted:
            found[int(current)] = record_from_manifest(
                raw,
                label=f"T098 record {current}",
                allowed_distribution_kinds=_T098_ALLOWED_DISTRIBUTIONS,
                allow_assistance_history=True,
            )
            if len(found) == len(wanted):
                return found
    missing = sorted(wanted - set(found))
    raise ValueError(f"T098 portable pool records were not found: {missing}")


def restore_t098_anchor(
    adapter: Any, record: BattleStartCheckpointRecord
) -> tuple[Any, dict[str, Any]]:
    """Restore an exact portable source record and return compact provenance."""

    if record.distribution_kind == ASSISTED_RUN_DISTRIBUTION_KIND:
        snapshot, method = restore_assisted_battle_start_record(adapter, record)
    else:
        snapshot, method = restore_battle_start_record(adapter, record)
    return snapshot, {
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_run_id": record.source_run_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "record_index": record.record_index,
        "restoration_method": method,
        "distribution_kind": record.distribution_kind,
    }


def reach_headbutt_known_top(
    adapter: Any,
    snapshot: Any,
    *,
    max_steps: int = 80,
) -> tuple[Any, dict[str, Any]]:
    """Use legal native actions until a Headbutt exact known-top state exists.

    This bounded driver does not predict transitions.  It observes the native
    input state, chooses only enumerated legal actions, and stops as soon as the
    public projection reports the required fact.
    """

    selected: list[dict[str, Any]] = []
    headbutt_played = False
    for step_index in range(max_steps + 1):
        projection = validate_public_information_projection(
            adapter.t096_public_information_projection(snapshot)
        )
        draw_order = projection["visibility"]["draw_order"]
        if draw_order.get("classification") == "known_prefix":
            prefix = draw_order.get("known_top_prefix")
            if isinstance(prefix, list) and prefix:
                return snapshot, {
                    "bounded_driver": "native-legal-headbutt-known-top-v1",
                    "steps": step_index,
                    "headbutt_played": headbutt_played,
                    "selected_actions": selected,
                }
        actions = adapter.legal_actions(snapshot)
        if not actions:
            raise RuntimeError("T098 Headbutt driver reached no legal actions")
        raw = snapshot.raw
        input_state = raw.get("battle_input_state")
        discard_nonempty = bool(raw.get("battle_discard_pile"))

        chosen = None
        if input_state == "CARD_SELECT" and headbutt_played:
            chosen = actions[0]
        elif input_state == "PLAYER_NORMAL":
            if discard_nonempty:
                chosen = next(
                    (action for action in actions if "Headbutt" in action.label),
                    None,
                )
            if chosen is None:
                chosen = next(
                    (
                        action
                        for action in actions
                        if action.kind == "card"
                        and "Headbutt" not in action.label
                        and "Defend" in action.label
                    ),
                    None,
                )
            if chosen is None:
                chosen = next(
                    (
                        action
                        for action in actions
                        if action.kind == "card" and "Headbutt" not in action.label
                    ),
                    None,
                )
            if chosen is None:
                chosen = next(
                    (action for action in actions if action.kind == "end_turn"),
                    None,
                )
        if chosen is None:
            chosen = actions[0]
        if "Headbutt" in chosen.label:
            headbutt_played = True
        selected.append(
            {
                "step": step_index,
                "input_state": input_state,
                "kind": chosen.kind,
                "label": chosen.label,
            }
        )
        transition = adapter.step(chosen)
        snapshot = transition.snapshot
        if transition.terminal or snapshot.raw.get("battle_active") is not True:
            raise RuntimeError("T098 Headbutt driver ended before a known-top state")
    raise RuntimeError("T098 Headbutt driver exhausted its bounded step budget")


def audit_t098_supported_witness(
    adapter: Any,
    snapshot: Any,
    *,
    family: str,
    witness_provenance: Mapping[str, Any],
    sampler_seed: int,
    expected_draw_classification: str,
    expected_intent_classification: str,
    diversity_expected: bool,
    particle_count: int = T098_PARTICLE_COUNT,
) -> dict[str, Any]:
    """Exercise native projection and sampler APIs for one supported witness."""

    if particle_count != T098_PARTICLE_COUNT:
        raise ValueError("T098 supported runtime witnesses require N=32")
    projection = validate_public_information_projection(
        adapter.t096_public_information_projection(snapshot)
    )
    if projection.get("information_fidelity") != "supported":
        raise T096SamplerError(f"T098 family {family} projection is not supported")
    visibility = projection["visibility"]
    draw_order = visibility["draw_order"]
    enemy_intent = visibility["enemy_intent"]
    if draw_order.get("classification") != expected_draw_classification:
        raise T096SamplerError(f"T098 family {family} draw classification mismatch")
    if enemy_intent.get("classification") != expected_intent_classification:
        raise T096SamplerError(f"T098 family {family} intent classification mismatch")

    particles = adapter.sample_hidden_future_particles(
        snapshot,
        sampler_seed=sampler_seed,
        particle_start=0,
        particle_count=particle_count,
    )
    if not isinstance(particles, Sequence) or isinstance(particles, (str, bytes)):
        raise T096SamplerError(f"T098 family {family} native batch is malformed")
    if len(particles) != particle_count:
        raise T096SamplerError(f"T098 family {family} native batch is incomplete")

    fingerprints: set[str] = set()
    next_cards: set[int] = set()
    public_parity = 0
    legal_parity = 0
    particle_indices: list[int] = []
    for expected_index, raw_row in enumerate(particles):
        if not isinstance(raw_row, Mapping):
            raise T096SamplerError(f"T098 family {family} particle is malformed")
        particle = dict(raw_row)
        if particle.get("particle_index") != expected_index:
            raise T096SamplerError(f"T098 family {family} particle index mismatch")
        particle_projection = validate_public_information_projection(
            particle.get("public_information_projection")
        )
        if compare_public_information(projection, particle_projection):
            public_parity += 1
        if public_action_identities(projection) == public_action_identities(
            particle_projection
        ):
            legal_parity += 1
        fingerprint = particle.get("hidden_future_fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise T096SamplerError(
                f"T098 family {family} particle lacks private audit digest"
            )
        fingerprints.add(fingerprint)
        next_card = particle.get("next_draw_card_id")
        if isinstance(next_card, int) and not isinstance(next_card, bool):
            next_cards.add(next_card)
        particle_indices.append(expected_index)
    if public_parity != particle_count or legal_parity != particle_count:
        raise T096SamplerError(f"T098 family {family} parity failed")
    if diversity_expected and len(fingerprints) < 2:
        raise T096SamplerError(f"T098 family {family} hidden diversity failed")

    preserved_facts: dict[str, Any] = {}
    if expected_draw_classification == "known_prefix":
        preserved_facts["known_top_prefix"] = draw_order.get("known_top_prefix")
    elif expected_draw_classification == "known_positions":
        preserved_facts["known_positions"] = draw_order.get("known_positions")
    elif expected_draw_classification == "full_public_exact":
        preserved_facts["visible_order_from_top"] = draw_order.get(
            "visible_order_from_top"
        )
    if expected_intent_classification == "hidden":
        forbidden = {
            "attacking",
            "intent_category",
            "current_move",
            "move_id",
            "move_base_damage",
            "move_hits",
        }
        monsters = projection.get("monsters")
        if not isinstance(monsters, list) or not monsters:
            raise T096SamplerError("T098 Runic Dome witness has no public monster")
        if any(forbidden & set(monster) for monster in monsters):
            raise T096SamplerError("T098 Runic Dome witness leaked current intent")
        if any(
            "last_move_id" not in monster or "public_statuses" not in monster
            for monster in monsters
        ):
            raise T096SamplerError(
                "T098 Runic Dome witness lost public history or statuses"
            )
        preserved_facts["monster_last_move_ids"] = [
            monster["last_move_id"] for monster in monsters
        ]
        preserved_facts["monster_public_statuses"] = [
            monster["public_statuses"] for monster in monsters
        ]

    return {
        "schema_id": T098_WITNESS_SCHEMA_ID,
        "family": family,
        "status": "PASS",
        "witness_provenance": dict(witness_provenance),
        "projection_schema_id": projection["schema_id"],
        "projection_sha256": canonical_sha256(projection),
        "information_fidelity": projection["information_fidelity"],
        "draw_order_classification": expected_draw_classification,
        "enemy_intent_classification": expected_intent_classification,
        "preserved_public_facts": preserved_facts,
        "sampler_seed": sampler_seed,
        "particle_count": particle_count,
        "accepted_particle_count": particle_count,
        "accepted_particle_indices": particle_indices,
        "public_projection_parity_pass_count": public_parity,
        "ordered_public_legal_action_parity_pass_count": legal_parity,
        "distinct_hidden_future_fingerprint_count": len(fingerprints),
        "distinct_next_draw_card_count": len(next_cards),
        "hidden_diversity_expected": diversity_expected,
        "hidden_diversity_pass": len(fingerprints) >= 2 if diversity_expected else None,
        "private_audit_fields_retained_in_report": False,
    }


def build_t098_unsupported_witness(
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize the native-owned timing-mixed fail-closed witness."""

    passed = all(
        audit.get(field) is True
        for field in (
            "runic_dome_hides_current_intent",
            "runic_dome_preserves_previous_move",
            "runic_dome_sanitizes_roll_misc",
            "runic_dome_hidden_counter_timing_invariant",
            "runic_dome_mixed_counter_sampler_fails_closed",
            "private_hidden_state_projection_invariant",
        )
    )
    return {
        "schema_id": T098_WITNESS_SCHEMA_ID,
        "family": "intentional_timing_mixed_unsupported",
        "status": "PASS" if passed else "FAIL",
        "witness_provenance": {
            "source": "StepSimulator.t096_visibility_audit",
            "native_constructed_case": "Runic Dome Book of Stabbing timing-mixed counter",
        },
        "information_fidelity": "unsupported_fidelity",
        "current_intent_hidden": audit.get("runic_dome_hides_current_intent"),
        "previous_move_retained": audit.get("runic_dome_preserves_previous_move"),
        "raw_hidden_roll_leaked": not bool(audit.get("runic_dome_sanitizes_roll_misc")),
        "sampler_rejected": audit.get("runic_dome_mixed_counter_sampler_fails_closed"),
        "private_variant_projection_invariant": audit.get(
            "runic_dome_hidden_counter_timing_invariant"
        ),
    }


def classify_t098(
    witnesses: Sequence[Mapping[str, Any]],
    unsupported: Mapping[str, Any],
) -> str:
    """Apply T098's task terminal classifications."""

    by_family = {str(row.get("family")): row for row in witnesses}
    ordinary = by_family.get("ordinary_hidden_draw_visible_intent")
    if ordinary is None or ordinary.get("status") != "PASS":
        return "PUBLIC_HIDDEN_FUTURE_SAMPLER_REGRESSION"
    if (
        by_family.get("supported_draw_knowledge", {}).get("status") != "PASS"
        or by_family.get("frozen_eye_exact_order", {}).get("status") != "PASS"
    ):
        return "DRAW_KNOWLEDGE_FIDELITY_INSUFFICIENT"
    if by_family.get("runic_dome_hidden_intent", {}).get("status") != "PASS":
        return "INTENT_VISIBILITY_FIDELITY_INSUFFICIENT"
    if unsupported.get("status") != "PASS":
        return "FAIL_CLOSED_BOUNDARY_INVALID"
    return "PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY"


def build_t098_report(
    *,
    implementation_head: str,
    native_identity: Mapping[str, Any],
    native_audit: Mapping[str, Any],
    witnesses: Sequence[Mapping[str, Any]],
    input_references: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the compact versioned task report."""

    audit = validate_t098_native_visibility_audit(native_audit)
    if native_identity.get("commit") != T098_NATIVE_COMMIT:
        raise ValueError("T098 native identity does not match the frozen commit")
    runtime = [dict(row) for row in witnesses]
    unsupported = build_t098_unsupported_witness(audit)
    terminal = classify_t098(runtime, unsupported)
    return {
        "schema_id": T098_REPORT_SCHEMA_ID,
        "task_id": T098_TASK_ID,
        "implementation_evidence_head": implementation_head,
        "native_identity": dict(native_identity),
        "projection_schema_id": "native-battle-public-information-v2",
        "visibility_audit_schema_id": T098_NATIVE_AUDIT_SCHEMA_ID,
        "input_references": dict(input_references),
        "sampling_budget": {
            "supported_runtime_witness_particle_count": T098_PARTICLE_COUNT,
            "meaning": "bounded semantic fidelity only; no convergence claim",
        },
        "supported_runtime_witnesses": runtime,
        "intentional_unsupported_witness": unsupported,
        "native_visibility_audit": audit,
        "private_field_leak_detected": any(
            row.get("private_audit_fields_retained_in_report") is True
            for row in runtime
        )
        or unsupported.get("raw_hidden_roll_leaked") is True,
        "terminal_classification": terminal,
        "non_claims": [
            "particle-count sufficiency",
            "exact posterior correctness",
            "arbitrary-mid-Battle universal support",
            "Search or controller improvement",
            "T034 completion",
        ],
    }


def write_t098_report(report: Mapping[str, Any], path: Path) -> dict[str, Any]:
    """Write and identify one compact canonical JSON report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(dict(report)) + "\n"
    path.write_text(payload, encoding="utf-8")
    return {
        "path": str(path.resolve()),
        "schema_id": T098_REPORT_SCHEMA_ID,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "byte_count": path.stat().st_size,
        "terminal_classification": report.get("terminal_classification"),
    }


def run_t098_fidelity_reentry(
    *,
    adapter_factory: Callable[[], Any],
    records: Mapping[str, BattleStartCheckpointRecord],
    implementation_head: str,
    native_identity: Mapping[str, Any],
    input_references: Mapping[str, Any],
) -> dict[str, Any]:
    """Run all bounded T098 witnesses against explicit portable records."""

    required = {"ordinary", "headbutt", "frozen_eye", "runic_dome"}
    if set(records) != required:
        raise ValueError(f"T098 record families must be exactly {sorted(required)}")
    adapter = adapter_factory()
    try:
        native_audit = validate_t098_native_visibility_audit(
            adapter.t096_visibility_audit()
        )
    finally:
        adapter.close()

    specifications = (
        (
            "ordinary",
            "ordinary_hidden_draw_visible_intent",
            "hidden",
            "public_exact",
            True,
            98001,
        ),
        (
            "frozen_eye",
            "frozen_eye_exact_order",
            "full_public_exact",
            "public_exact",
            False,
            98003,
        ),
        (
            "runic_dome",
            "runic_dome_hidden_intent",
            "hidden",
            "hidden",
            True,
            98004,
        ),
    )
    witnesses: list[dict[str, Any]] = []
    for key, family, draw, intent, diversity, seed in specifications:
        adapter = adapter_factory()
        try:
            snapshot, provenance = restore_t098_anchor(adapter, records[key])
            witnesses.append(
                audit_t098_supported_witness(
                    adapter,
                    snapshot,
                    family=family,
                    witness_provenance=provenance,
                    sampler_seed=seed,
                    expected_draw_classification=draw,
                    expected_intent_classification=intent,
                    diversity_expected=diversity,
                )
            )
        finally:
            adapter.close()

    adapter = adapter_factory()
    try:
        snapshot, provenance = restore_t098_anchor(adapter, records["headbutt"])
        snapshot, driver = reach_headbutt_known_top(adapter, snapshot)
        provenance["runtime_driver"] = driver
        witnesses.insert(
            1,
            audit_t098_supported_witness(
                adapter,
                snapshot,
                family="supported_draw_knowledge",
                witness_provenance=provenance,
                sampler_seed=98002,
                expected_draw_classification="known_prefix",
                expected_intent_classification="public_exact",
                diversity_expected=True,
            ),
        )
    finally:
        adapter.close()

    return build_t098_report(
        implementation_head=implementation_head,
        native_identity=native_identity,
        native_audit=native_audit,
        witnesses=witnesses,
        input_references=input_references,
    )
