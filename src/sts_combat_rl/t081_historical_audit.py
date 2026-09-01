"""Deterministic, annotation-only audit of the retained T043 dependency chain."""

import json
from pathlib import Path
from typing import Any
from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
    evaluate_eligibility,
)

SCHEMA_VERSION = "t081-historical-claim-boundary-audit-v1"

_ROWS = (
    (
        "T044",
        "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3",
        "t043-main-runs1000-assist_0-s4",
        "diagnostic_mechanism",
        "checkpoint-conditional evaluation; no generalized model-quality claim",
        "historical T044 numerical outcomes remain unchanged; four trainer rows",
    ),
    (
        "T047",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional search-mechanism result",
        "trainer scale and broad coverage unavailable; exact historical result only",
    ),
    (
        "T048",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke; T046 cohort",
        "diagnostic_mechanism",
        "checkpoint-conditional search-mechanism result",
        "current-T046 evidence family; trainer scale unavailable",
    ),
    (
        "T048",
        "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3",
        "t043-main-runs1000-assist_0-s4; runs1000 assist_0 cohort",
        "diagnostic_mechanism",
        "checkpoint-conditional search-mechanism result",
        "upstream naming is not trainer scale",
    ),
    (
        "T050",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional complete-run mechanism evidence",
        "no generalized learned-quality claim",
    ),
    (
        "T051",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional source/reachability evidence",
        "upstream run count is not trainer scale",
    ),
    (
        "T052",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional fixed-cohort comparison",
        "historical numerical result is retained; model-quality generalization unavailable",
    ),
    (
        "T062",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional tree-internal Search v2 mechanism evidence",
        "full_simulator_state_oracle_like diagnostic only; not learned-quality or generalized evidence",
    ),
    (
        "T070",
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "t043-assist_0-smoke",
        "diagnostic_mechanism",
        "checkpoint-conditional Search v2 audit; not learned-quality evidence",
        "four trainer rows; filename naming is not evidence of scale",
    ),
)


def build_audit() -> dict[str, Any]:
    quality = ()
    rows = []
    for task, sha, evidence_family, mode, claim, limitations in _ROWS:
        facts = {
            "trainer_record_count": Fact(4),
            "teacher_record_count": Fact.unavailable(
                "not retained in the cited task/PR records"
            ),
            "override_kind": Fact("smoke"),
            "source_pool_runs": Fact.unavailable(
                "upstream run count is not a trainer fact"
            ),
        }
        artifact = ArtifactQualification(
            {
                "id": "t043-assist_0-smoke"
                if sha.startswith("a231")
                else "t043-main-runs1000-assist_0-s4",
                "kind": "checkpoint",
                "schema": "unavailable",
            },
            facts,
            {"sha256": sha, "identity_source": "retained task contract / PR record"},
        )
        decisions = {}
        identity = {
            "artifact_id": artifact.artifact["id"],
            "artifact_kind": "checkpoint",
            "sha256": sha,
        }
        for reuse, boundary, predicates in (
            ("historical_reproduction", "exact historical dependency", ()),
            (
                "diagnostic_mechanism",
                claim,
                (Predicate("trainer_record_count", "min", 1),),
            ),
            (
                "scientific_quality_claim",
                "new generalized model-quality claim",
                quality,
            ),
        ):
            decisions[reuse] = evaluate_eligibility(
                artifact,
                EligibilityRequirements(reuse, boundary, predicates, **identity),
            )
        rows.append(
            {
                "task": task,
                "evidence_family": evidence_family,
                "historical_use": mode,
                "maximum_justified_claim": claim,
                "limitations": limitations,
                "integrity": artifact.integrity,
                "qualification": artifact.to_dict()["facts"],
                "consumer_decisions": decisions,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "source": "retained T043/T044/T047-T070 task and PR records",
            "missing_facts": "unavailable facts remain explicit; filenames never substitute for provenance",
        },
        "claims": rows,
    }


def write_audit(path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(build_audit(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    write_audit(parser.parse_args().path)
