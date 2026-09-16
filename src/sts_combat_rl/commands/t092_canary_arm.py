"""Private child process for exactly one isolated, authorized T092 arm.

This command is not a user-facing launcher.  The parent command validates
authorization first and supplies one JSON request over stdin.  It intentionally
imports one native extension once, verifies that binary, and never attempts a
module unload/reload or a path swap.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import record_from_manifest
from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import run_t092_native_canary_arm
from sts_combat_rl.sim.t092_canary_execution import write_t092_canary_json
from sts_combat_rl.sim.t092_canary_process import (
    T092_CANARY_ARM_REQUEST_SCHEMA_ID,
    T092CanaryProcessError,
    validate_t092_arm_process_spec,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _request(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema_id", "schema_version", "task_id", "arm", "implementation_head",
        "worker", "spec", "source", "selected", "canonical",
    }:
        raise T092CanaryProcessError("T092 isolated arm request has an unexpected shape")
    arm = raw.get("arm")
    if (
        raw.get("schema_id") != T092_CANARY_ARM_REQUEST_SCHEMA_ID
        or raw.get("schema_version") != 1
        or raw.get("task_id") != "T092"
        or arm not in {"OFF", "ON"}
        or not isinstance(raw.get("implementation_head"), str)
        or len(raw["implementation_head"]) != 40
        or not isinstance(raw.get("worker"), Mapping)
        or not isinstance(raw.get("spec"), Mapping)
        or not isinstance(raw.get("source"), Mapping)
        or not isinstance(raw.get("selected"), Mapping)
        or not isinstance(raw.get("canonical"), Mapping)
    ):
        raise T092CanaryProcessError("T092 isolated arm request is invalid")
    return dict(raw)


def _verified_native_binary(
    spec: Mapping[str, Any], *, arm: str, implementation_head: str
) -> dict[str, Any]:
    """Resolve exactly one extension before any adapter/simulator construction."""

    validated = validate_t092_arm_process_spec(
        spec, arm=arm, implementation_head=implementation_head
    )
    if "slaythespire" in sys.modules:
        raise T092CanaryProcessError("T092 arm process already imported a native extension")
    module = importlib.import_module("slaythespire")
    module_path = Path(str(getattr(module, "__file__", ""))).resolve()
    expected = Path(validated["extension_path"]).resolve()
    if module_path != expected or _sha256_file(module_path) != validated["extension_sha256"]:
        raise T092CanaryProcessError("T092 arm resolved a mismatched native extension")
    if module_path.stat().st_size != validated["extension_size_bytes"]:
        raise T092CanaryProcessError("T092 arm native extension size mismatches")
    return {
        "path": str(module_path),
        "sha256": validated["extension_sha256"],
        "size_bytes": validated["extension_size_bytes"],
    }


def execute_one_arm(request: Mapping[str, Any]) -> dict[str, Any]:
    """Execute an already-authorized request after native identity admission."""

    raw = _request(request)
    arm = str(raw["arm"])
    binary = _verified_native_binary(
        raw["spec"], arm=arm, implementation_head=str(raw["implementation_head"])
    )
    try:
        source = T090SplitEntry(**dict(raw["source"]))
        selected = T085BattleStartRecord.from_mapping(raw["selected"])
        canonical = record_from_manifest(
            raw["canonical"],
            label="T092 isolated arm canonical checkpoint",
            allowed_distribution_kinds=frozenset({"natural_run", "assisted_run"}),
            allow_assistance_history=True,
        )
    except (TypeError, ValueError) as exc:
        raise T092CanaryProcessError("T092 isolated arm restore request is malformed") from exc
    if selected.selection_identity != source.source_identity or canonical.source_checkpoint_id != source.source_identity:
        raise T092CanaryProcessError("T092 isolated arm source/restore identity mismatches")
    # Imported only after the extension check above.  Construction occurs in the
    # arm runner and therefore cannot happen on a binary identity mismatch.
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    return run_t092_native_canary_arm(
        source=source,
        selected=selected,
        canonical=canonical,
        telemetry_enabled=arm == "ON",
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"),
        worker=raw["worker"],
        implementation_head=str(raw["implementation_head"]),
        native_binary=binary,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sts_combat_rl.commands.t092_canary_arm")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = json.loads(sys.stdin.read())
        record = execute_one_arm(request)
        write_t092_canary_json(args.output, record, schema_id=record["schema_id"])
    except (json.JSONDecodeError, OSError, T092CanaryProcessError, ValueError) as exc:
        print(f"T092 isolated arm failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
