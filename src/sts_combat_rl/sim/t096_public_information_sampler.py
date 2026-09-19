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


def audit_native_particles(
    adapter: Any,
    snapshot: Any,
    *,
    sampler_seed: int,
    particle_count: int,
    require_distribution_reference: bool = True,
) -> dict[str, Any]:
    """Audit one native anchor without exposing private rows to controllers."""

    if (
        isinstance(particle_count, bool)
        or not isinstance(particle_count, int)
        or particle_count <= 0
    ):
        raise T096SamplerError("T096 particle_count must be positive")
    anchor = validate_public_information_projection(
        adapter.t096_public_information_projection(snapshot)
    )
    particles = adapter.sample_hidden_future_particles(
        snapshot,
        sampler_seed=sampler_seed,
        particle_count=particle_count,
    )
    if len(particles) != particle_count:
        raise T096SamplerError("native sampler returned the wrong particle count")
    action_parity_passes = 0
    public_parity_passes = 0
    fingerprints: set[str] = set()
    next_cards: Counter[int] = Counter()
    rejected = 0
    for index, row in enumerate(particles):
        if not isinstance(row, Mapping):
            raise T096SamplerError(f"native particle {index} is not a mapping")
        projection = validate_public_information_projection(
            row.get("public_information_projection")
        )
        if compare_public_information(anchor, projection):
            public_parity_passes += 1
        else:
            rejected += 1
            continue
        if public_action_identities(anchor) == public_action_identities(projection):
            action_parity_passes += 1
        else:
            rejected += 1
            continue
        fingerprint = row.get("hidden_future_fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise T096SamplerError(
                f"native particle {index} lacks private diversity digest"
            )
        fingerprints.add(fingerprint)
        card_id = row.get("next_draw_card_id")
        if card_id is not None:
            if isinstance(card_id, bool) or not isinstance(card_id, int):
                raise T096SamplerError(f"native particle {index} has invalid next card")
            next_cards[card_id] += 1

    if public_parity_passes != particle_count or action_parity_passes != particle_count:
        raise T096SamplerError("T096 public or legal-action parity failed")
    if len(fingerprints) < 2:
        raise T096SamplerError("T096 particles lack future-dynamics hidden diversity")
    result: dict[str, Any] = {
        "schema_id": T096_SAMPLER_SCHEMA_ID,
        "sampler_seed": sampler_seed,
        "particle_count": particle_count,
        "public_parity_pass_count": public_parity_passes,
        "legal_action_parity_pass_count": action_parity_passes,
        "rejected_particle_count": rejected,
        "distinct_hidden_future_fingerprint_count": len(fingerprints),
        "next_card_empirical_counts": dict(sorted(next_cards.items())),
        "public_projection_sha256": canonical_sha256(anchor),
    }
    if require_distribution_reference:
        reference = analytic_next_card_multiset(dict(snapshot.raw))
        if sum(next_cards.values()) != particle_count:
            raise T096SamplerError("T096 particle next-card evidence is incomplete")
        tv = total_variation(next_cards, reference)
        result["analytic_next_card_counts"] = dict(sorted(reference.items()))
        result["next_card_total_variation"] = tv
        result["distribution_pass"] = bool(tv <= T096_TV_LIMIT)
    else:
        result["distribution_pass"] = None
    return result


def classify_t096(
    results: Sequence[Mapping[str, Any]], *, fidelity_gaps: Sequence[str] = ()
) -> str:
    """Apply the frozen terminal order to already validated anchor reports."""

    if not results:
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
