"""Versioned, fail-closed scientific artifact qualification."""

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "artifact-eligibility-v1"
UNKNOWN = {"status": "unavailable"}


def _json(value: Any) -> Any:
    if isinstance(value, Fact):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"value is not JSON-safe: {type(value).__name__}")


@dataclass(frozen=True)
class Fact:
    """A qualification fact; unavailable is deliberate and never imputed."""

    value: Any = None
    available: bool = True
    reason: str | None = None

    @classmethod
    def unavailable(cls, reason: str = "fact unavailable") -> "Fact":
        return cls(available=False, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        result = {"status": "known" if self.available else "unavailable"}
        if self.available:
            result["value"] = _json(self.value)
        if self.reason is not None:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class ArtifactQualification:
    artifact: dict[str, Any]
    facts: dict[str, Fact]
    integrity: dict[str, Any] = field(default_factory=dict)
    producer_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "artifact": _json(self.artifact),
                "integrity": _json(self.integrity),
                "facts": {k: self.facts[k].to_dict() for k in sorted(self.facts)},
                "producer_scope": self.producer_scope}


@dataclass(frozen=True)
class Predicate:
    fact: str
    operator: str = "equals"
    required: Any = True

    def to_dict(self) -> dict[str, Any]:
        return {"fact": self.fact, "operator": self.operator, "required": _json(self.required)}


@dataclass(frozen=True)
class EligibilityRequirements:
    reuse_mode: str
    claim_boundary: str
    predicates: tuple[Predicate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"reuse_mode": self.reuse_mode, "claim_boundary": self.claim_boundary,
                "predicates": [p.to_dict() for p in self.predicates]}


def _check(observed: Any, operator: str, required: Any) -> bool:
    if operator == "equals": return observed == required
    if operator == "not_equals": return observed != required
    if operator == "min": return isinstance(observed, (int, float)) and observed >= required
    if operator == "contains": return required in observed
    if operator == "in": return observed in required
    raise ValueError(f"unsupported eligibility predicate operator: {operator}")


def evaluate_eligibility(qualification: ArtifactQualification,
                         requirements: EligibilityRequirements) -> dict[str, Any]:
    if requirements.reuse_mode not in {"historical_reproduction", "diagnostic_mechanism", "scientific_quality_claim"}:
        raise ValueError(f"unknown reuse mode: {requirements.reuse_mode}")
    predicates = []
    requested = requirements.predicates
    # Quality claims require an explicit treatment of an active smoke/debug
    # override; omission is intentionally fail-closed.
    override = qualification.facts.get("override_kind")
    if (requirements.reuse_mode == "scientific_quality_claim" and override
            and override.available and override.value in {"smoke", "debug"}
            and not any(p.fact == "override_kind" for p in requested)):
        requested = requested + (Predicate("override_kind", "not_equals", override.value),)
    for predicate in requested:
        fact = qualification.facts.get(predicate.fact)
        if fact is None or not fact.available:
            result, reason, observed = False, "required fact unavailable", UNKNOWN
        else:
            observed = fact.value
            result = _check(observed, predicate.operator, predicate.required)
            reason = "satisfied" if result else "observed fact does not satisfy requirement"
        predicates.append({"fact": predicate.fact, "observed": _json(observed),
                           "required": _json(predicate.required), "result": result,
                           "reason": reason})
    return {"schema_version": SCHEMA_VERSION, "eligible": all(p["result"] for p in predicates),
            "artifact": qualification.to_dict(), "requirements": requirements.to_dict(),
            "predicates": predicates, "reuse_mode": requirements.reuse_mode,
            "claim_boundary": requirements.claim_boundary}
