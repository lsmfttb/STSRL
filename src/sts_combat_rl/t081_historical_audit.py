"""Deterministic, annotation-only audit of the retained T043 dependency chain."""

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "t081-historical-claim-boundary-audit-v1"

_ROWS = (
    ("T044", "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3", "diagnostic_mechanism", "checkpoint-conditional evaluation; no generalized model-quality claim", "historical T044 numerical outcomes remain unchanged; four trainer rows"),
    ("T047", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "diagnostic_mechanism", "checkpoint-conditional search-mechanism result", "trainer scale and broad coverage unavailable; exact historical result only"),
    ("T048", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "diagnostic_mechanism", "checkpoint-conditional search-mechanism result", "trainer scale and broad coverage unavailable"),
    ("T050", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "diagnostic_mechanism", "checkpoint-conditional complete-run mechanism evidence", "no generalized learned-quality claim"),
    ("T051", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "diagnostic_mechanism", "checkpoint-conditional source/reachability evidence", "upstream run count is not trainer scale"),
    ("T052", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "diagnostic_mechanism", "checkpoint-conditional fixed-cohort comparison", "historical numerical result is retained; model-quality generalization unavailable"),
    ("T062", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4", "historical_reproduction", "reproduce/audit the exact historical dependency only", "no retained evidence of scale-qualified T043 training"),
    ("T070", "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3", "diagnostic_mechanism", "checkpoint-conditional Search v2 audit; not learned-quality evidence", "four trainer rows; runs1000 names upstream pool only"),
)


def build_audit() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": {"source": "retained T043/T044/T047-T070 task and PR records", "missing_facts": "reported as unavailable; no filename inference"},
        "claims": [
            {"task": task, "checkpoint_sha256": sha, "qualification": {"trainer_record_count": 4, "override_kind": "smoke", "upstream_source_pool": "unavailable" if task in {"T047", "T048", "T050"} else "runs1000" if task in {"T051", "T070"} else "unavailable"}, "historical_use": mode, "maximum_justified_claim": claim, "limitations": limitations}
            for task, sha, mode, claim, limitations in _ROWS
        ],
    }


def write_audit(path: str | Path) -> None:
    Path(path).write_text(json.dumps(build_audit(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
