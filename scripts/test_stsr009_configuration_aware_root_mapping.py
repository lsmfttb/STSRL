#!/usr/bin/env python3
"""STSRL-owned acceptance of STSRL-009 from the verifier's disposable build."""

from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path

from sts_combat_rl.sim.t110_configuration_aware_mapping import (
    AUDIT_PREDICATES,
    validate_t110_configuration_mapping_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True)
    args = parser.parse_args()
    module = import_module("slaythespire")
    if (
        not Path(module.__file__)
        .resolve()
        .is_relative_to(Path(args.build_dir).resolve())
    ):
        raise SystemExit("STSRL-009 imported module outside disposable build")
    sim = module.StepSimulator(module.CharacterClass.IRONCLAD, 1, 20)
    for call in (
        lambda: sim.sample_hidden_future_particles_search(
            17, 0, 2, 1, False, "injection"
        ),
        lambda: sim.sample_hidden_future_particles_search(
            17, 0, 2, 1, False, injection="injection"
        ),
        lambda: sim.stsr009_configuration_aware_root_mapping_audit("injection"),
    ):
        try:
            call()
        except TypeError:
            continue
        raise SystemExit("STSRL-009 production caller selected failure injection")
    audit = validate_t110_configuration_mapping_audit(
        sim.stsr009_configuration_aware_root_mapping_audit()
    )
    for predicate in AUDIT_PREDICATES:
        print(f"{predicate}={str(audit[predicate]).lower()}")
    print(
        "STSRL-009 exact-source configuration mapping, isolation, and native audit passed"
    )


if __name__ == "__main__":
    main()
