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
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact": _json(self.artifact),
            "integrity": _json(self.integrity),
            "facts": {k: self.facts[k].to_dict() for k in sorted(self.facts)},
            "producer_scope": self.producer_scope,
        }


@dataclass(frozen=True)
class Predicate:
    fact: str
    operator: str = "equals"
    required: Any = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact,
            "operator": self.operator,
            "required": _json(self.required),
        }


@dataclass(frozen=True)
class EligibilityRequirements:
    reuse_mode: str
    claim_boundary: str
    predicates: tuple[Predicate, ...]
    artifact_id: str | None = None
    artifact_kind: str | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reuse_mode": self.reuse_mode,
            "claim_boundary": self.claim_boundary,
            "predicates": [p.to_dict() for p in self.predicates],
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "sha256": self.sha256,
        }


def _check(observed: Any, operator: str, required: Any) -> bool:
    if operator == "equals":
        return observed == required
    if operator == "not_equals":
        return observed != required
    if operator == "min":
        return isinstance(observed, (int, float)) and observed >= required
    if operator == "contains":
        return required in observed
    if operator == "in":
        return observed in required
    raise ValueError(f"unsupported eligibility predicate operator: {operator}")


def evaluate_eligibility(
    qualification: ArtifactQualification, requirements: EligibilityRequirements
) -> dict[str, Any]:
    if requirements.reuse_mode not in {
        "historical_reproduction",
        "diagnostic_mechanism",
        "scientific_quality_claim",
    }:
        raise ValueError(f"unknown reuse mode: {requirements.reuse_mode}")
    predicates = []
    requested = requirements.predicates
    if (
        requirements.artifact_id is None
        or requirements.artifact_kind is None
        or requirements.sha256 is None
    ):
        predicates.append(
            {
                "fact": "artifact_identity_requirements",
                "observed": UNKNOWN,
                "required": "complete",
                "result": False,
                "reason": "required artifact identity omitted",
            }
        )
    identity = (
        ("artifact.id", qualification.artifact.get("id"), requirements.artifact_id),
        (
            "artifact.kind",
            qualification.artifact.get("kind"),
            requirements.artifact_kind,
        ),
        (
            "integrity.sha256",
            qualification.integrity.get("sha256"),
            requirements.sha256,
        ),
    )
    for fact_name, observed, required in identity:
        if required is not None:
            predicates.append(
                {
                    "fact": fact_name,
                    "observed": _json(observed) if observed is not None else UNKNOWN,
                    "required": required,
                    "result": observed == required,
                    "reason": "satisfied"
                    if observed == required
                    else "missing or mismatched artifact identity",
                }
            )
    if requirements.reuse_mode == "scientific_quality_claim":
        scale = any("count" in p.fact or "scale" in p.fact for p in requested)
        coverage = any(
            "coverage" in p.fact or p.fact.startswith("source.") for p in requested
        )
        if not scale:
            predicates.append(
                {
                    "fact": "explicit_scale_predicate",
                    "observed": UNKNOWN,
                    "required": "consumer-provided",
                    "result": False,
                    "reason": "required scale predicate omitted",
                }
            )
        if not coverage:
            predicates.append(
                {
                    "fact": "explicit_coverage_predicate",
                    "observed": UNKNOWN,
                    "required": "consumer-provided",
                    "result": False,
                    "reason": "required coverage predicate omitted",
                }
            )
        # Override status is itself a required quality fact unless the
        # consumer explicitly supplies a predicate for it.
        override = qualification.facts.get("override_kind")
        if override is None or not override.available:
            requested = requested + (Predicate("override_kind", "equals", "none"),)
        elif override.value != "none":
            predicates.append(
                {
                    "fact": "override_kind",
                    "observed": override.value,
                    "required": "none",
                    "result": False,
                    "reason": "quality claims disallow smoke/debug/named overrides",
                }
            )
    for predicate in requested:
        fact = qualification.facts.get(predicate.fact)
        if fact is None or not fact.available:
            result, reason, observed = False, "required fact unavailable", UNKNOWN
        else:
            observed = fact.value
            result = _check(observed, predicate.operator, predicate.required)
            reason = (
                "satisfied" if result else "observed fact does not satisfy requirement"
            )
        predicates.append(
            {
                "fact": predicate.fact,
                "observed": _json(observed),
                "required": _json(predicate.required),
                "result": result,
                "reason": reason,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "eligible": all(p["result"] for p in predicates),
        "artifact": qualification.to_dict(),
        "requirements": requirements.to_dict(),
        "predicates": predicates,
        "reuse_mode": requirements.reuse_mode,
        "claim_boundary": requirements.claim_boundary,
    }
