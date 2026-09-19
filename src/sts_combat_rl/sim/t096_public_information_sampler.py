"""T096 public-information sampler audit primitives.

The simulator owns hidden-state construction.  This module only validates the
native result, compares public projections, and computes the preregistered
bounded next-card distribution statistic.  It never writes hidden state or
reimplements Slay the Spire mechanics.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

T096_TASK_ID = "T096"
T096_PUBLIC_INFORMATION_SCHEMA_ID = "native-battle-public-information-v1"
T096_SAMPLER_SCHEMA_ID = "native-hidden-future-sampler-v1"
T096_ANCHOR_METADATA_SCHEMA_ID = "native-battle-anchor-distribution-audit-v1"
T096_SPLIT_DOMAIN = "T096-PUBLIC-INFORMATION-SAMPLER-V1"
T096_PARTICLES_PER_ANCHOR = 8192
T096_TV_LIMIT = 0.05

_REQUIRED_PROJECTION_KEYS = frozenset(
    {
        "schema_id",
        "information_regime",
        "screen_identity",
        "act",
        "floor_num",
        "encounter_id",
        "turn",
        "input_state",
        "battle_outcome",
        "player",
        "hand",
        "discard_pile",
        "exhaust_pile",
        "draw_pile_size",
        "monsters",
        "persistent_resources",
        "visibility",
        "ordered_public_legal_actions",
        "draw_pile_membership",
    }
)
_FORBIDDEN_PRIVATE_KEY_FRAGMENTS = (
    "rng",
    "seed",
    "future_fingerprint",
    "next_draw",
    "private_state",
    "hidden_state",
)


class T096SamplerError(ValueError):
    """Fail-closed T096 input or native-output error."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_public_information_projection(value: object) -> dict[str, Any]:
    """Validate the versioned public projection and its no-private firewall."""

    if not isinstance(value, Mapping):
        raise T096SamplerError("T096 public projection must be a mapping")
    projection = dict(value)
    unknown = set(projection) - _REQUIRED_PROJECTION_KEYS
    missing = _REQUIRED_PROJECTION_KEYS - set(projection)
    if unknown or missing:
        raise T096SamplerError(
            f"T096 projection keys mismatch; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
    if projection["schema_id"] != T096_PUBLIC_INFORMATION_SCHEMA_ID:
        raise T096SamplerError("T096 projection schema is not current")
    if projection["information_regime"] != "normal_information":
        raise T096SamplerError("T096 projection has the wrong information regime")
    if projection["screen_identity"] != "BATTLE":
        raise T096SamplerError("T096 sampler only accepts Battle projections")
    _assert_no_private_keys(projection, path="projection")
    visibility = projection["visibility"]
    if not isinstance(visibility, Mapping):
        raise T096SamplerError("T096 projection visibility must be a mapping")
    _require_classification(visibility, "draw_order", "hidden")
    _require_classification(visibility, "enemy_intent", "public_exact")
    _require_classification(visibility, "draw_knowledge", "unsupported_fidelity")
    _require_classification(
        visibility, "intent_hidden_mechanics", "unsupported_fidelity"
    )
    actions = projection["ordered_public_legal_actions"]
    if not isinstance(actions, list):
        raise T096SamplerError("T096 ordered public actions must be a list")
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            raise T096SamplerError(f"T096 action {index} is not a mapping")
        expected = {"scope", "kind", "idx1", "idx2", "idx3", "label"}
        if set(action) != expected:
            raise T096SamplerError(
                f"T096 action {index} identity keys are not public-only"
            )
        if not isinstance(action.get("label"), str):
            raise T096SamplerError(f"T096 action {index} label is not text")
        if "bits=" in action["label"]:
            raise T096SamplerError(
                f"T096 action {index} label contains replay-only native bits"
            )
    return projection


def _assert_no_private_keys(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()
            if any(fragment in name for fragment in _FORBIDDEN_PRIVATE_KEY_FRAGMENTS):
                raise T096SamplerError(
                    f"private key {path}.{key} leaked into projection"
                )
            _assert_no_private_keys(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_no_private_keys(child, path=f"{path}[{index}]")


def _require_classification(
    visibility: Mapping[str, Any], field: str, expected: str
) -> None:
    value = visibility.get(field)
    if not isinstance(value, Mapping) or value.get("classification") != expected:
        raise T096SamplerError(
            f"T096 visibility.{field} must be classified {expected!r}"
        )


def compare_public_information(anchor: Mapping[str, Any], particle: object) -> bool:
    """Compare two already validated public projections exactly."""

    return canonical_json(anchor) == canonical_json(
        validate_public_information_projection(particle)
    )


def public_action_identities(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = projection.get("ordered_public_legal_actions")
    if not isinstance(value, list):
        raise T096SamplerError("T096 ordered public action list is missing")
    return [dict(action) for action in value]


def _card_id(row: object, label: str) -> int:
    if not isinstance(row, Mapping):
        raise T096SamplerError(f"{label} is not a card mapping")
    value = row.get("id")
    if isinstance(value, bool) or not isinstance(value, int):
        raise T096SamplerError(f"{label}.id is not an integer")
    return value


def analytic_next_card_multiset(snapshot_raw: Mapping[str, Any]) -> Counter[int]:
    """Build the frozen eligible-family reference from public anchor data."""

    hand = snapshot_raw.get("battle_hand")
    discard = snapshot_raw.get("battle_discard_pile")
    exhaust = snapshot_raw.get("battle_exhaust_pile")
    deck = snapshot_raw.get("deck")
    if not isinstance(hand, list) or not isinstance(discard, list):
        raise T096SamplerError("T096 anchor lacks current hand/discard evidence")
    if not isinstance(exhaust, list) or discard or exhaust:
        raise T096SamplerError("T096 distribution anchor has non-empty discard/exhaust")
    if not isinstance(deck, list) or not deck:
        raise T096SamplerError("T096 anchor lacks persistent deck evidence")
    deck_ids = Counter(_card_id(card, "deck card") for card in deck)
    hand_ids = Counter(_card_id(card, "hand card") for card in hand)
    if hand_ids - deck_ids:
        raise T096SamplerError("T096 hand contains card absent from persistent deck")
    unseen = deck_ids - hand_ids
    draw_size = snapshot_raw.get("battle_draw_pile_size")
    if (
        isinstance(draw_size, bool)
        or not isinstance(draw_size, int)
        or draw_size != sum(unseen.values())
    ):
        raise T096SamplerError("T096 draw pile does not partition the persistent deck")
    if not unseen or not 2 <= len(unseen) <= 32:
        raise T096SamplerError(
            "T096 anchor is outside the frozen 2..32 identity family"
        )
    return unseen


def total_variation(
    empirical: Mapping[int, int], reference: Mapping[int, int]
) -> float:
    total = sum(empirical.values())
    reference_total = sum(reference.values())
    if total <= 0 or reference_total <= 0:
        raise T096SamplerError("T096 TV requires non-empty empirical/reference counts")
    identities = set(empirical) | set(reference)
    return 0.5 * sum(
        abs(
            empirical.get(identity, 0) / total
            - reference.get(identity, 0) / reference_total
        )
        for identity in identities
    )


def validate_anchor_distribution_metadata(value: object) -> dict[str, Any]:
    """Validate native-owned proof for the frozen distribution family."""

    if not isinstance(value, Mapping):
        raise T096SamplerError("T096 anchor distribution metadata must be a mapping")
    metadata = dict(value)
    if metadata.get("schema_id") != T096_ANCHOR_METADATA_SCHEMA_ID:
        raise T096SamplerError(
            "T096 anchor distribution metadata schema is not current"
        )
    bool_fields = (
        "eligible",
        "first_ordinary_player_decision",
        "stronger_draw_constraint",
        "discard_empty",
        "exhaust_empty",
        "all_cards_persistent_deck_instances",
        "no_temporary_generated_inserted_cards",
        "multiset_union_exact",
        "remaining_unseen_nonempty",
    )
    for field in bool_fields:
        if not isinstance(metadata.get(field), bool):
            raise T096SamplerError(f"T096 anchor metadata {field} is not boolean")
    if metadata.get("draw_order_visibility") != "hidden":
        raise T096SamplerError("T096 anchor draw order is not classified hidden")
    if metadata.get("draw_knowledge_fidelity") != "ordinary-hidden-draw-only":
        raise T096SamplerError("T096 anchor draw knowledge fidelity is unsupported")
    for field in (
        "deck_size",
        "hand_size",
        "draw_pile_size",
        "remaining_unseen_card_identity_count",
    ):
        value_int = metadata.get(field)
        if (
            isinstance(value_int, bool)
            or not isinstance(value_int, int)
            or value_int < 0
        ):
            raise T096SamplerError(f"T096 anchor metadata {field} is invalid")
    if metadata["hand_size"] + metadata["draw_pile_size"] != metadata["deck_size"]:
        raise T096SamplerError("T096 hand and draw sizes do not partition the deck")
    counts = metadata.get("remaining_unseen_card_counts")
    if not isinstance(counts, Mapping):
        raise T096SamplerError("T096 anchor metadata lacks unseen-card multiset")
    normalized_counts: dict[int, int] = {}
    for identity, count in counts.items():
        if isinstance(identity, bool) or not isinstance(identity, int):
            raise T096SamplerError("T096 unseen card identity is not an integer")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise T096SamplerError("T096 unseen card multiplicity is invalid")
        normalized_counts[int(identity)] = int(count)
    if metadata["remaining_unseen_card_identity_count"] != len(normalized_counts):
        raise T096SamplerError("T096 unseen identity count disagrees with multiset")
    if metadata["draw_pile_size"] != sum(normalized_counts.values()):
        raise T096SamplerError("T096 unseen multiset disagrees with draw-pile size")
    if not 2 <= len(normalized_counts) <= 32:
        raise T096SamplerError(
            "T096 anchor is outside the frozen 2..32 identity family"
        )
    required_true = (
        "eligible",
        "first_ordinary_player_decision",
        "discard_empty",
        "exhaust_empty",
        "all_cards_persistent_deck_instances",
        "no_temporary_generated_inserted_cards",
        "multiset_union_exact",
        "remaining_unseen_nonempty",
    )
    if any(not metadata[field] for field in required_true):
        raise T096SamplerError("T096 native anchor metadata does not prove eligibility")
    if metadata["stronger_draw_constraint"]:
        raise T096SamplerError("T096 anchor has a stronger draw-order constraint")
    metadata["remaining_unseen_card_counts"] = dict(sorted(normalized_counts.items()))
    return metadata


def _incomplete_particle_result(
    *,
    sampler_seed: int,
    particle_count: int,
    attempted: int = 0,
    rejected: int = 0,
    rejection_reasons: Mapping[str, int] | None = None,
    failure_code: str,
    failure_message: str,
) -> dict[str, Any]:
    return {
        "schema_id": T096_SAMPLER_SCHEMA_ID,
        "status": "INCOMPLETE",
        "terminal_hint": "INCOMPLETE",
        "failure_code": failure_code,
        "failure_message": failure_message,
        "sampler_seed": sampler_seed,
        "particle_count": particle_count,
        "accepted_particle_count": 0,
        "attempted_particle_count": attempted,
        "rejected_particle_count": rejected,
        "rejection_reason_counts": dict(sorted((rejection_reasons or {}).items())),
        "public_parity_pass_count": 0,
        "legal_action_parity_pass_count": 0,
        "distribution_pass": None,
    }


def audit_native_particles(
    adapter: Any,
    snapshot: Any,
    *,
    sampler_seed: int,
    particle_count: int,
    require_distribution_reference: bool = True,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Audit one native anchor, retaining exactly ``particle_count`` accepts."""

    try:
        if (
            isinstance(particle_count, bool)
            or not isinstance(particle_count, int)
            or particle_count <= 0
        ):
            raise T096SamplerError("T096 particle_count must be positive")
        if max_attempts is None:
            max_attempts = particle_count * 4
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < particle_count
        ):
            raise T096SamplerError("T096 max_attempts must be at least particle_count")
        anchor = validate_public_information_projection(
            adapter.t096_public_information_projection(snapshot)
        )
        metadata = validate_anchor_distribution_metadata(
            adapter.t096_anchor_distribution_metadata(snapshot)
        )
        reference = metadata["remaining_unseen_card_counts"]
        accepted: list[Mapping[str, Any]] = []
        fingerprints: set[str] = set()
        accepted_indices: set[int] = set()
        accepted_seeds: list[int] = []
        next_cards: Counter[int] = Counter()
        rejection_reasons: Counter[str] = Counter()
        attempted = 0
        particle_start = 0
        while len(accepted) < particle_count and attempted < max_attempts:
            request_count = min(
                1024,
                particle_count - len(accepted),
                max_attempts - attempted,
            )
            try:
                particles = adapter.sample_hidden_future_particles(
                    snapshot,
                    sampler_seed=sampler_seed,
                    particle_start=particle_start,
                    particle_count=request_count,
                )
            except Exception as exc:  # noqa: BLE001 - fail-closed audit boundary
                return _incomplete_particle_result(
                    sampler_seed=sampler_seed,
                    particle_count=particle_count,
                    attempted=attempted,
                    rejected=attempted,
                    rejection_reasons={"native_sampler_exception": attempted or 1},
                    failure_code="native_sampler_exception",
                    failure_message=str(exc),
                )
            if not isinstance(particles, Sequence) or isinstance(
                particles, (str, bytes)
            ):
                return _incomplete_particle_result(
                    sampler_seed=sampler_seed,
                    particle_count=particle_count,
                    attempted=attempted,
                    rejected=attempted,
                    failure_code="malformed_native_batch",
                    failure_message="native sampler batch is not a sequence",
                )
            if not particles:
                break
            attempted += len(particles)
            particle_start += len(particles)
            for index, row in enumerate(particles):
                reason = ""
                if not isinstance(row, Mapping):
                    reason = "malformed_particle"
                else:
                    try:
                        projection = validate_public_information_projection(
                            row.get("public_information_projection")
                        )
                        if not compare_public_information(anchor, projection):
                            reason = "public_projection_mismatch"
                        elif public_action_identities(anchor) != (
                            public_action_identities(projection)
                        ):
                            reason = "legal_action_mismatch"
                        elif not isinstance(
                            row.get("hidden_future_fingerprint"), str
                        ) or not row.get("hidden_future_fingerprint"):
                            reason = "missing_hidden_digest"
                        elif row.get("next_draw_card_id") is None:
                            reason = "missing_next_card"
                        elif isinstance(
                            row.get("next_draw_card_id"), bool
                        ) or not isinstance(row.get("next_draw_card_id"), int):
                            reason = "invalid_next_card"
                        elif (
                            isinstance(row.get("particle_index"), bool)
                            or not isinstance(row.get("particle_index"), int)
                            or row.get("particle_index") < 0
                        ):
                            reason = "invalid_particle_index"
                        elif row.get("particle_index") in accepted_indices:
                            reason = "duplicate_particle_index"
                        elif (
                            isinstance(row.get("sampler_seed"), bool)
                            or not isinstance(row.get("sampler_seed"), int)
                        ):
                            reason = "invalid_particle_seed"
                    except Exception:  # noqa: BLE001 - malformed native row is rejected
                        reason = "malformed_particle"
                if reason:
                    rejection_reasons[reason] += 1
                    continue
                accepted.append(row)
                fingerprints.add(str(row["hidden_future_fingerprint"]))
                next_cards[int(row["next_draw_card_id"])] += 1
                accepted_indices.add(int(row["particle_index"]))
                accepted_seeds.append(int(row["sampler_seed"]))
                if len(accepted) >= particle_count:
                    break
        if len(accepted) < particle_count:
            return _incomplete_particle_result(
                sampler_seed=sampler_seed,
                particle_count=particle_count,
                attempted=attempted,
                rejected=sum(rejection_reasons.values()),
                rejection_reasons=rejection_reasons,
                failure_code="insufficient_accepted_particles",
                failure_message=(
                    f"accepted {len(accepted)} of required {particle_count} "
                    f"within max_attempts={max_attempts}"
                ),
            )
        if len(fingerprints) < 2:
            return _incomplete_particle_result(
                sampler_seed=sampler_seed,
                particle_count=particle_count,
                attempted=attempted,
                rejected=sum(rejection_reasons.values()),
                rejection_reasons=rejection_reasons,
                failure_code="hidden_future_diversity_failure",
                failure_message="accepted particles have fewer than two hidden digests",
            )
        result: dict[str, Any] = {
            "schema_id": T096_SAMPLER_SCHEMA_ID,
            "status": "COMPLETE",
            "terminal_hint": "COMPLETE",
            "sampler_seed": sampler_seed,
            "particle_count": particle_count,
            "accepted_particle_count": particle_count,
            "attempted_particle_count": attempted,
            "rejected_particle_count": sum(rejection_reasons.values()),
            "rejection_reason_counts": dict(sorted(rejection_reasons.items())),
            "accepted_particle_indices": [
                int(row["particle_index"]) for row in accepted
            ],
            "accepted_particle_seeds": accepted_seeds,
            "particle_seed_mapping": {
                "domain": T096_SPLIT_DOMAIN,
                "sampler_seed": sampler_seed,
                "particle_indices": [int(row["particle_index"]) for row in accepted],
            },
            "public_parity_pass_count": particle_count,
            "legal_action_parity_pass_count": particle_count,
            "distinct_hidden_future_fingerprint_count": len(fingerprints),
            "next_card_empirical_counts": dict(sorted(next_cards.items())),
            "public_projection_sha256": canonical_sha256(anchor),
            "anchor_distribution_metadata": metadata,
        }
        if require_distribution_reference:
            if sum(next_cards.values()) != particle_count:
                return _incomplete_particle_result(
                    sampler_seed=sampler_seed,
                    particle_count=particle_count,
                    attempted=attempted,
                    rejected=sum(rejection_reasons.values()),
                    rejection_reasons=rejection_reasons,
                    failure_code="missing_next_card_evidence",
                    failure_message=(
                        "accepted particles do not have complete next-card evidence"
                    ),
                )
            tv = total_variation(next_cards, reference)
            result["analytic_next_card_counts"] = dict(sorted(reference.items()))
            result["next_card_total_variation"] = tv
            result["distribution_pass"] = bool(tv <= T096_TV_LIMIT)
        else:
            result["distribution_pass"] = None
        return result
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed report
        return _incomplete_particle_result(
            sampler_seed=sampler_seed,
            particle_count=particle_count if isinstance(particle_count, int) else 0,
            failure_code="audit_exception",
            failure_message=str(exc),
        )


def classify_t096(
    results: Sequence[Mapping[str, Any]], *, fidelity_gaps: Sequence[str] = ()
) -> str:
    """Apply the frozen terminal order to already validated anchor reports."""

    if not results:
        return "INCOMPLETE"
    if any(row.get("status") == "INCOMPLETE" for row in results):
        return "INCOMPLETE"
    required = {
        "public_parity_pass_count",
        "legal_action_parity_pass_count",
        "particle_count",
        "distribution_pass",
    }
    if any(not required.issubset(row) for row in results):
        return "INCOMPLETE"
    if any(
        not isinstance(row.get("public_parity_pass_count"), int)
        or row.get("public_parity_pass_count", 0) != row.get("particle_count")
        for row in results
    ):
        return "PUBLIC_HIDDEN_FUTURE_SAMPLER_PARITY_INVALID"
    if any(
        not isinstance(row.get("legal_action_parity_pass_count"), int)
        or row.get("legal_action_parity_pass_count", 0) != row.get("particle_count")
        for row in results
    ):
        return "PUBLIC_HIDDEN_FUTURE_SAMPLER_PARITY_INVALID"
    if any(row.get("distribution_pass") is False for row in results):
        return "PUBLIC_HIDDEN_FUTURE_SAMPLER_DISTRIBUTION_INVALID"
    if fidelity_gaps:
        return "NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT"
    if len(results) < 4 or any(
        row.get("particle_count") != T096_PARTICLES_PER_ANCHOR for row in results
    ):
        return "INCOMPLETE"
    if not all(row.get("distribution_pass") is True for row in results):
        return "INCOMPLETE"
    return "PUBLIC_HIDDEN_FUTURE_SAMPLER_PILOT_READY"


def finite_tv(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
