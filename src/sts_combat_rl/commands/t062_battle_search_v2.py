"""Input-contract preflight for the T062 Battle Search v2 experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


T062_INPUT_PREFLIGHT_SCHEMA_ID = "t062-battle-search-v2-input-preflight-v1"
T061_RETENTION_MANIFEST_SHA256 = (
    "2fb5e329505b52541edbd7aa74b5fa2025e97276523ee341884538a4d7b3ef90"
)
T052_COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
T052_COHORT_BYTES = 161435825
T043_CHECKPOINT_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)
T043_CHECKPOINT_BYTES = 386717


def run_t062_input_preflight_from_paths(
    *,
    output_path: Path,
    t061_retention_manifest_path: Path,
    t052_cohort_path: Path,
    t043_checkpoint_path: Path,
) -> dict[str, Any]:
    """Verify all immutable T062 input identities before any model call."""

    artifacts = {
        "t061_retention_manifest": _verify_t061_retention_manifest(
            t061_retention_manifest_path
        ),
        "t052_fixed_cohort": _verify_file(
            t052_cohort_path,
            expected_sha256=T052_COHORT_SHA256,
            expected_bytes=T052_COHORT_BYTES,
        ),
        "t043_checkpoint": _verify_file(
            t043_checkpoint_path,
            expected_sha256=T043_CHECKPOINT_SHA256,
            expected_bytes=T043_CHECKPOINT_BYTES,
        ),
    }
    problems = [
        f"{label}: {problem}"
        for label, identity in artifacts.items()
        for problem in identity["problems"]
    ]
    manifest_payload: dict[str, Any] | None = None
    if not artifacts["t061_retention_manifest"]["problems"]:
        try:
            raw = json.loads(t061_retention_manifest_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("must be a JSON object")
            if raw.get("schema_id") != "t061-retention-manifest-v2":
                raise ValueError("has an unsupported schema_id")
            retention_root = raw.get("retention_root")
            if not isinstance(retention_root, str) or not retention_root:
                raise ValueError("omits retention_root")
            manifest_payload = {
                "schema_id": raw["schema_id"],
                "retention_root": retention_root,
                "raw_artifacts_may_be_deleted_when": raw.get(
                    "raw_artifacts_may_be_deleted_when"
                ),
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"t061_retention_manifest: invalid manifest: {exc}")

    report = {
        "schema_id": T062_INPUT_PREFLIGHT_SCHEMA_ID,
        "task_id": "T062",
        "input_artifacts": artifacts,
        "t061_retention_contract": manifest_payload,
        "command_passed": not problems,
        "problems": problems,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def format_t062_input_preflight_report(report: dict[str, Any]) -> str:
    """Format the fail-closed input-contract preflight for stderr."""

    lines = [
        "T062 Battle Search v2 input preflight",
        f"command passed: {'yes' if report.get('command_passed') else 'no'}",
    ]
    for label, identity in report.get("input_artifacts", {}).items():
        lines.append(
            f"{label}: sha256={identity.get('sha256', '(missing)')}, "
            f"bytes={identity.get('bytes', '(missing)')}"
        )
    if report.get("problems"):
        lines.append("problems:")
        lines.extend(f"  {problem}" for problem in report["problems"])
    return "\n".join(lines)


def _verify_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    if not path.is_file():
        problems.append("required file does not exist")
        return {
            "path": str(path),
            "expected_sha256": expected_sha256,
            "expected_bytes": expected_bytes,
            "sha256": None,
            "bytes": None,
            "problems": problems,
        }
    byte_count = path.stat().st_size
    actual = _sha256_file(path)
    if actual != expected_sha256:
        problems.append("sha256 does not match the published T062 contract")
    if expected_bytes is not None and byte_count != expected_bytes:
        problems.append("byte count does not match the published T062 contract")
    return {
        "path": str(path),
        "expected_sha256": expected_sha256,
        "expected_bytes": expected_bytes,
        "sha256": actual,
        "bytes": byte_count,
        "problems": problems,
    }


def _verify_t061_retention_manifest(path: Path) -> dict[str, Any]:
    """Verify T061's documented canonical self-hash, not its raw file hash."""

    identity = _verify_file(path, expected_sha256="")
    identity["expected_sha256"] = T061_RETENTION_MANIFEST_SHA256
    if not path.is_file():
        return identity
    identity["problems"] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("must be a JSON object")
        manifest_identity = raw.get("manifest_identity")
        if not isinstance(manifest_identity, dict):
            raise ValueError("omits manifest_identity")
        if manifest_identity.get("sha256") != T061_RETENTION_MANIFEST_SHA256:
            identity["problems"].append(
                "manifest_identity.sha256 does not match the published T062 contract"
            )
        if manifest_identity.get("bytes") != path.stat().st_size:
            identity["problems"].append(
                "manifest_identity.bytes does not match the on-disk file"
            )
        canonical = dict(raw)
        canonical_identity = dict(manifest_identity)
        canonical_identity["bytes"] = None
        canonical_identity["sha256"] = None
        canonical["manifest_identity"] = canonical_identity
        canonical_bytes = (
            json.dumps(canonical, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        identity["canonical_sha256"] = canonical_sha256
        if canonical_sha256 != T061_RETENTION_MANIFEST_SHA256:
            identity["problems"].append(
                "canonical retention-manifest self-hash does not match the published T062 contract"
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        identity["problems"].append(f"invalid retention manifest: {exc}")
    return identity


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
