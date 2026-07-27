#!/usr/bin/env python3
"""Audit the exact native T062 callback call/consume dependency boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


EXPECTED_NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(
            f"T068 refuses to overwrite native-source audit: {args.output}"
        )
    source = _git_show(args.native_repository, "bindings/slaythespire.cpp")
    searcher = _git_show(
        args.native_repository, "src/sim/search/BattleScumSearcher2.cpp"
    )
    required = (
        "const auto priors = raw.cast<std::vector<double>>();",
        "const double value = callback(",
        "auto priors = policyPriorFnc(bc, actions);",
        "const double evaluation = learnedLeafValueFnc(curState, legalActions);",
        "node.policyPriors = std::move(priors);",
        "updateFromEvaluation(searchStack, actionStack, evaluation);",
    )
    combined = source + "\n" + searcher
    missing = [marker for marker in required if marker not in combined]
    if missing:
        raise SystemExit(
            "T068 native callback dependency markers missing: " + "; ".join(missing)
        )
    payload = {
        "schema_id": "t068-native-callback-source-audit-v1",
        "schema_version": 1,
        "task_id": "T068",
        "native_repository": str(args.native_repository),
        "native_commit": EXPECTED_NATIVE_COMMIT,
        "files": {
            "bindings/slaythespire.cpp": hashlib.sha256(source.encode()).hexdigest(),
            "src/sim/search/BattleScumSearcher2.cpp": hashlib.sha256(
                searcher.encode()
            ).hexdigest(),
        },
        "synchronous_return_required": True,
        "callback_dependency": {
            "policy": "Python callback casts and returns priors before applyPolicyPriors assigns node.policyPriors.",
            "value": "Python callback casts and returns value before updateFromEvaluation performs backup.",
            "simultaneous_requests_allowed": False,
            "conclusion": "No second callback request can be ready before the current callback response is consumed by native traversal.",
        },
        "command_passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def _git_show(repository: Path, path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{EXPECTED_NATIVE_COMMIT}:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"cannot read native source {path}")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
