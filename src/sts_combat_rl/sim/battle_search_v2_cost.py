"""T067 cost attribution and semantic-preserving node inference cache.

The cache is deliberately process-local and scoped to one native search call.
Its key contains every public model input plus the occurrence-safe ordered legal
action identities.  A canonical payload is retained beside the digest so a
digest collision fails closed instead of returning a possibly unrelated model
result.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from time import perf_counter
from typing import Any, Callable

from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceInferenceResult,
)


T067_COST_ATTRIBUTION_SCHEMA_ID = "t067-battle-search-v2-cost-attribution-v1"
T067_COST_ATTRIBUTION_SCHEMA_VERSION = 1
T067_CACHE_KEY_SCHEMA_ID = "t067-public-node-cache-key-v1"
T067_REPAIR_IDENTITY = "exact-public-node-inference-cache-v1"


@dataclass(frozen=True)
class CacheScoreResult:
    result: SearchGuidanceInferenceResult
    cache_hit: bool
    cache_lookup_ms: float
    scorer_time_ms: float
    cache_key: str | None


class PublicNodeInferenceCache:
    """Bounded exact-result cache for one Battle Search v2 invocation."""

    def __init__(self, capacity: int = 4096) -> None:
        if capacity <= 0:
            raise ValueError("T067 inference cache capacity must be positive")
        self.capacity = int(capacity)
        self._entries: OrderedDict[str, tuple[bytes, SearchGuidanceInferenceResult]] = (
            OrderedDict()
        )
        self.lookup_count = 0
        self.hit_count = 0
        self.miss_count = 0
        self.uncacheable_count = 0
        self.eviction_count = 0
        self.eviction_time_ms = 0.0

    def score(
        self,
        context: DecisionContext,
        scorer: Callable[[DecisionContext], SearchGuidanceInferenceResult],
    ) -> CacheScoreResult:
        started = perf_counter()
        self.lookup_count += 1
        key = public_node_cache_key(context)
        if key is None:
            self.uncacheable_count += 1
            self.miss_count += 1
            lookup_ms = (perf_counter() - started) * 1000.0
            scorer_started = perf_counter()
            result = scorer(context)
            return CacheScoreResult(
                result=result,
                cache_hit=False,
                cache_lookup_ms=lookup_ms,
                scorer_time_ms=(perf_counter() - scorer_started) * 1000.0,
                cache_key=None,
            )

        digest, payload = key
        cached = self._entries.get(digest)
        if cached is not None:
            cached_payload, result = cached
            if cached_payload != payload:
                # A digest collision is not safe to resolve by choosing one
                # entry.  Evict the colliding entry and score uncached.
                del self._entries[digest]
                self.miss_count += 1
                lookup_ms = (perf_counter() - started) * 1000.0
                scorer_started = perf_counter()
                result = scorer(context)
                return CacheScoreResult(
                    result=result,
                    cache_hit=False,
                    cache_lookup_ms=lookup_ms,
                    scorer_time_ms=(perf_counter() - scorer_started) * 1000.0,
                    cache_key=None,
                )
            self._entries.move_to_end(digest)
            self.hit_count += 1
            return CacheScoreResult(
                result=result,
                cache_hit=True,
                cache_lookup_ms=(perf_counter() - started) * 1000.0,
                scorer_time_ms=0.0,
                cache_key=digest,
            )

        self.miss_count += 1
        lookup_ms = (perf_counter() - started) * 1000.0
        scorer_started = perf_counter()
        result = scorer(context)
        scorer_ms = (perf_counter() - scorer_started) * 1000.0
        self._entries[digest] = (payload, result)
        self._entries.move_to_end(digest)
        if len(self._entries) > self.capacity:
            eviction_started = perf_counter()
            self._entries.popitem(last=False)
            self.eviction_count += 1
            self.eviction_time_ms += (perf_counter() - eviction_started) * 1000.0
        return CacheScoreResult(
            result=result,
            cache_hit=False,
            cache_lookup_ms=lookup_ms,
            scorer_time_ms=scorer_ms,
            cache_key=digest,
        )

    def telemetry(self) -> dict[str, float]:
        return {
            "cache_capacity": float(self.capacity),
            "cache_lookup_count": float(self.lookup_count),
            "cache_hit_count": float(self.hit_count),
            "cache_miss_count": float(self.miss_count),
            "cache_uncacheable_count": float(self.uncacheable_count),
            "cache_eviction_count": float(self.eviction_count),
            "cache_eviction_ms": self.eviction_time_ms,
            "cache_entry_count": float(len(self._entries)),
        }


def public_node_cache_key(
    context: DecisionContext,
) -> tuple[str, bytes] | None:
    """Return a collision-checked digest basis for one public node context.

    ``None`` means the public context cannot be represented by the current
    canonical schema.  Callers must score it without caching; they may not
    guess or drop fields.
    """

    actions = context.tactical_legal_actions
    if len(actions) != len(context.legal_action_features):
        return None
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            return None
        identity = action.get("identity")
        if not isinstance(identity, Mapping):
            return None
        if not isinstance(identity.get("stable_id"), str):
            return None
        occurrence = identity.get("occurrence")
        if not isinstance(occurrence, int) or isinstance(occurrence, bool):
            return None
        if identity.get("stable_id") == "":
            return None
        # Require the identity itself in the payload and retain ordering.  The
        # index check prevents a future caller from accidentally dropping an
        # action row while preserving the same unordered set of identities.
        if index < 0:
            return None

    payload = {
        "schema_id": T067_CACHE_KEY_SCHEMA_ID,
        "screen_state": context.screen_state,
        "snapshot_features": context.snapshot_features,
        "legal_action_features": context.legal_action_features,
        "legal_action_kinds": context.legal_action_kinds,
        "eligible_action_indices": context.eligible_action_indices,
        "snapshot_metadata": context.snapshot_metadata,
        "legal_action_metadata": context.legal_action_metadata,
        "tactical_state": context.tactical_state,
        "tactical_legal_actions": actions,
        "tactical_feature_schema_id": context.tactical_feature_schema_id,
        "public_run_context": context.public_run_context,
    }
    try:
        canonical = _canonical_json(payload)
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(canonical).hexdigest(), canonical


def _canonical_json(value: Any) -> bytes:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("cache key contains non-finite float")
        return value
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda pair: str(pair[0]))
        normalized: dict[str, Any] = {}
        for key, item in items:
            normalized_key = str(key)
            if normalized_key in normalized:
                raise ValueError("cache key contains colliding mapping keys")
            normalized[normalized_key] = _normalize(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    raise TypeError(f"cache key contains unsupported value {type(value).__name__}")
