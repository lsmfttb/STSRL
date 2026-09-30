#!/usr/bin/env python3
"""Smoke the T107 diagnostic and audit against a disposable native build."""

from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path

from sts_combat_rl.sim.t099_particle_search_bridge import (
    validate_t099_particle_search_bridge,
)
from sts_combat_rl.sim.t105_native_stage_observability import (
    validate_t105_stage_trace,
)
from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    AUDIT_PREDICATES,
    AUDIT_SCHEMA,
    DIAGNOSTIC_SCHEMA,
    validate_t107_mapping_audit,
)


def _rejects_injection(call, label: str) -> None:
    try:
        call()
    except TypeError:
        return
    raise SystemExit(f"production native API accepted test injection: {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True)
    args = parser.parse_args()

    build_root = Path(args.build_dir).resolve()
    module = import_module("slaythespire")
    module_path = Path(module.__file__).resolve()
    if not module_path.is_relative_to(build_root):
        raise SystemExit(f"imported module is outside disposable build: {module_path}")
    sim = module.StepSimulator(module.CharacterClass.IRONCLAD, 1, 20)

    validate_t105_stage_trace(
        sim.last_particle_search_stage_diagnostics(), expected_status="not_attempted"
    )
    bridge_call = sim.sample_hidden_future_particles_search
    _rejects_injection(
        lambda: bridge_call(17, 0, 1, 1, False, "ROOT_MAPPING_NO_PUBLIC_ACTIONS"),
        "extra positional bridge argument",
    )
    _rejects_injection(
        lambda: bridge_call(
            17, 0, 1, 1, False, injection="ROOT_MAPPING_NO_PUBLIC_ACTIONS"
        ),
        "keyword bridge argument",
    )
    _rejects_injection(
        lambda: sim.stsr008_root_occurrence_mapping_audit(
            "ROOT_MAPPING_NO_PUBLIC_ACTIONS"
        ),
        "caller-selected audit injection",
    )

    bridge = validate_t099_particle_search_bridge(bridge_call(17, 0, 2, 1, False))
    trace = validate_t105_stage_trace(
        sim.last_particle_search_stage_diagnostics(),
        expected_status="accepted",
        particle_start=0,
        particle_count=2,
    )
    for row in trace["particles"]:
        diagnostic = row["root_occurrence_mapping_diagnostic"]
        if not isinstance(diagnostic, dict):
            raise SystemExit("successful native mapping diagnostic is absent")
        if (
            diagnostic.get("schema_id") != DIAGNOSTIC_SCHEMA
            or diagnostic.get("status") != "completed"
            or diagnostic.get("mapping_subreason") != "mapping_completed"
        ):
            raise SystemExit("successful native mapping diagnostic is inconsistent")
    if len(bridge["particles"]) != 2:
        raise SystemExit("accepted STSRL-006 semantic report changed shape")

    audit = validate_t107_mapping_audit(sim.stsr008_root_occurrence_mapping_audit())
    if audit["schema_id"] != AUDIT_SCHEMA or any(
        audit[name] is not True for name in AUDIT_PREDICATES
    ):
        raise SystemExit("native STSRL-008 fixed audit did not pass")
    print("STSRL-008 exact-source diagnostic, isolation, and native audit passed")


if __name__ == "__main__":
    main()
