"""Qualify retained T111 inputs and prepare, but do not start, execution.

The preparation command revalidates the historical T101/T087/T085 bindings
and current T110 source pin. It has no simulator adapter construction path.
Candidate execution remains a separately reviewed Maintainer action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import sysconfig
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands import t088_canary, t103_particle_diagnostic
from sts_combat_rl.commands.t088_canary import T088CanaryPathError
from sts_combat_rl.commands.t103_particle_diagnostic import T103PathError
from sts_combat_rl.sim.lightspeed_source import (
    default_lightspeed_source_manifest_path,
    load_lightspeed_source_manifest,
)
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_RESTORE_SCHEMA_ID,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    T101IncompleteError,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111ConfiguredSearchError,
)

T111_APPROVED_SPEC_COMMIT = "f8ceef6f68bab587f7696d9230fbffd7416b19b2"
T111_QUALIFICATION_SCHEMA = "t111-input-qualification-v1"
T111_READINESS_PREPARATION_SCHEMA = "t111-execution-readiness-preparation-v1"
T111_PREPARATION_MANIFEST_SCHEMA = "t111-preparation-retention-manifest-v1"
T111_DEFAULT_RETENTION_MANIFEST = Path(
    "/mnt/d/DeadlyCatCoding/STSRL/artifacts/"
    "t101-bounded-particle-convergence-361a77d/admission/"
    "t101-terminal-retention-manifest.json"
)
T111_INPUT_INELIGIBLE = "CONFIGURED_SEARCH_DOMAIN_INPUT_INELIGIBLE"


class T111QualificationError(ValueError):
    """T111 input qualification or preparation failed closed."""


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).rstrip(b"\n")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _windows_gitdir_pointer(cwd: Path) -> bool:
    """Return true only for a Windows absolute gitdir in a worktree .git file."""

    for directory in (cwd, *cwd.parents):
        marker = directory / ".git"
        try:
            if not marker.is_file():
                continue
            content = marker.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue
        match = re.fullmatch(r"gitdir:\s*([A-Za-z]:[/\\].+)", content)
        if match is not None:
            return True
    return False


def _wsl_windows_path(path: Path) -> str:
    result = subprocess.run(
        ["wslpath", "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    converted = result.stdout.strip()
    if not re.fullmatch(r"[A-Za-z]:\\.+", converted):
        raise T111QualificationError("wslpath did not return an absolute Windows path")
    return converted


def _wsl_posix_path(path: str) -> Path:
    result = subprocess.run(
        ["wslpath", "-u", path],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    converted = result.stdout.strip()
    if not converted.startswith("/"):
        raise T111QualificationError("wslpath did not return an absolute POSIX path")
    return Path(converted)


def _git_output(path: Path, *arguments: str, text: bool = True) -> str | bytes:
    """Run Git normally; use Windows Git only for a proven WSL worktree pointer.

    The fallback never masks an ordinary Git failure. It is enabled only on a
    POSIX runtime when an ancestor contains a `.git` file with a Windows
    absolute gitdir path, as produced by a Windows-managed linked worktree.
    """

    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=True,
            capture_output=True,
            text=text,
            timeout=30 if arguments and arguments[0] == "show" else 10,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        if sys.platform == "win32" or not _windows_gitdir_pointer(path):
            raise
        try:
            windows_path = _wsl_windows_path(path)
            result = subprocess.run(
                ["git.exe", "-C", windows_path, *arguments],
                check=True,
                capture_output=True,
                text=text,
                timeout=30 if arguments and arguments[0] == "show" else 10,
            )
            return result.stdout
        except (
            OSError,
            subprocess.SubprocessError,
            T111QualificationError,
        ) as fallback_error:
            raise T111QualificationError(
                "POSIX Git failed and the Windows-managed worktree fallback failed"
            ) from fallback_error


def _git_repository_root(path: Path) -> Path:
    """Resolve and validate the Git root containing a retained input path."""

    try:
        resolved = path.resolve(strict=True)
        cwd = resolved if resolved.is_dir() else resolved.parent
        root_value = _git_output(cwd, "rev-parse", "--show-toplevel")
        assert isinstance(root_value, str)
        root_text = root_value.strip()
        if sys.platform != "win32" and re.match(r"^[A-Za-z]:[/\\]", root_text):
            root = _wsl_posix_path(root_text).resolve(strict=True)
        else:
            root = Path(root_text).resolve(strict=True)
    except (OSError, subprocess.SubprocessError, T111QualificationError) as exc:
        raise T111QualificationError(
            "cannot resolve retained-input Git repository root"
        ) from exc
    if not root.is_dir():
        raise T111QualificationError("retained-input Git repository root is invalid")
    return root


def _python_runtime_fingerprint() -> dict[str, object]:
    """Identify the active interpreter and extension ABI without importing it."""

    executable = Path(sys.executable).resolve()
    return {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "major": sys.version_info.major,
        "minor": sys.version_info.minor,
        "soabi": sysconfig.get_config_var("SOABI"),
        "extension_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
        "platform": sysconfig.get_platform(),
        "executable": str(executable),
    }


def _validate_native_binary_abi_path(
    binary_path: Path, runtime: Mapping[str, object]
) -> Path:
    """Fail closed unless a native extension filename matches this runtime ABI."""

    if dict(runtime) != _python_runtime_fingerprint():
        raise T111QualificationError("authorized Python runtime identity changed")
    suffix = runtime.get("extension_suffix")
    if (
        runtime.get("implementation") != "CPython"
        or not isinstance(suffix, str)
        or not suffix
        or not binary_path.name.endswith(suffix)
    ):
        raise T111QualificationError(
            "native extension ABI suffix does not match the active CPython runtime"
        )
    try:
        resolved = binary_path.resolve(strict=True)
        if not resolved.is_file():
            raise OSError("native extension path is not a regular file")
    except OSError as exc:
        raise T111QualificationError("native extension binary is unavailable") from exc
    return resolved


def _artifact_binding(
    path_value: object, *, schema_id: object, sha256: object, size_bytes: object
) -> dict[str, object]:
    if (
        not isinstance(path_value, str)
        or not path_value
        or not isinstance(schema_id, str)
        or not schema_id
        or not isinstance(sha256, str)
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256)
        or isinstance(size_bytes, bool)
        or not isinstance(size_bytes, int)
        or size_bytes < 0
    ):
        raise T111QualificationError("retained artifact binding is malformed")
    return {
        "path": path_value,
        "schema_id": schema_id,
        "sha256": sha256,
        "size_bytes": size_bytes,
    }


def _verify_file_binding(
    binding: Mapping[str, object], *, role: str
) -> dict[str, object]:
    path = Path(str(binding["path"]))
    try:
        resolved = path.resolve(strict=True)
        size = resolved.stat().st_size
    except OSError as exc:
        raise T111QualificationError(f"retained input missing: {role}") from exc
    if size != binding["size_bytes"] or _sha256_file(resolved) != binding["sha256"]:
        raise T111QualificationError(f"retained input hash/size mismatch: {role}")
    return {
        **dict(binding),
        "resolved_path": str(resolved),
        "verification": "sha256_and_size_match",
    }


def _verify_t088_gate_reference(
    binding: Mapping[str, object], *, observed: Mapping[str, object], role: str
) -> dict[str, object]:
    """Normalize a T088 byte-count reference against its T101 binding.

    T088's accepted input gate emits `byte_count`; T101 retention bindings use
    `size_bytes`. The schema and all other identity fields remain exact, and
    the referenced on-disk file is independently rehashed and stat-checked.
    """

    expected_schema = binding.get("schema_id")
    expected_sha256 = binding.get("sha256")
    expected_size = binding.get("size_bytes")
    byte_count = observed.get("byte_count")
    optional_size_bytes = observed.get("size_bytes")
    observed_path_value = observed.get("path")
    if (
        not isinstance(expected_schema, str)
        or observed.get("schema_id") != expected_schema
        or not isinstance(expected_sha256, str)
        or observed.get("sha256") != expected_sha256
        or isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or expected_size < 0
        or isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count < 0
        or byte_count != expected_size
        or (
            "size_bytes" in observed
            and (
                isinstance(optional_size_bytes, bool)
                or not isinstance(optional_size_bytes, int)
                or optional_size_bytes != byte_count
            )
        )
        or not isinstance(observed_path_value, str)
        or not observed_path_value
    ):
        raise T111QualificationError(f"T088 gate identity differs for {role}")
    verified = _verify_file_binding(binding, role=role)
    observed_path = Path(observed_path_value)
    try:
        resolved_observed_path = observed_path.resolve(strict=True)
        observed_size = resolved_observed_path.stat().st_size
    except OSError as exc:
        raise T111QualificationError(
            f"T088 gate artifact path is unavailable: {role}"
        ) from exc
    if (
        resolved_observed_path != Path(str(verified["resolved_path"]))
        or observed_size != byte_count
    ):
        raise T111QualificationError(
            f"T088 gate path or actual byte count differs for {role}"
        )
    return {
        **dict(binding),
        "resolved_path": str(resolved_observed_path),
        "verification": "accepted_t088_gate_schema_sha256_path_and_size_match",
    }


def _verify_historical_manifest_blob(
    binding: Mapping[str, object], *, producer_commit: str, repo_root: Path
) -> dict[str, object]:
    if (
        producer_commit != "361a77dbe88b2215a92cfe96e4f4c5c243f7ff1c"
        or binding.get("schema_id") != "sts-lightspeed-source-manifest-v1"
    ):
        raise T111QualificationError("historical T101 manifest producer is unexpected")
    try:
        blob = _git_output(
            repo_root,
            "show",
            f"{producer_commit}:docs/sts_lightspeed_source_manifest.json",
            text=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise T111QualificationError(
            "exact historical T101 manifest Git blob is unavailable"
        ) from exc
    if not isinstance(blob, bytes):
        raise T111QualificationError("historical T101 manifest Git blob is not bytes")
    digest = hashlib.sha256(blob).hexdigest()
    if len(blob) != binding["size_bytes"] or digest != binding["sha256"]:
        raise T111QualificationError(
            "historical T101 manifest Git blob hash/size mismatch"
        )
    try:
        document = json.loads(blob)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T111QualificationError(
            "historical T101 manifest Git blob is not valid JSON"
        ) from exc
    if (
        not isinstance(document, Mapping)
        or document.get("schema_id") != binding["schema_id"]
    ):
        raise T111QualificationError("historical T101 manifest schema mismatch")
    return {
        **dict(binding),
        "resolved_path": None,
        "verification": "exact_producer_git_blob_sha256_and_size_match",
        "historical_producer_commit": producer_commit,
    }


def _source_manifest_identity(
    path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    manifest = load_lightspeed_source_manifest(path)
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    if identity != {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T111_NATIVE_REF,
        "commit": T111_NATIVE_COMMIT,
    }:
        raise T111QualificationError("current source manifest does not select T110")
    if "native_stsr009_configuration_aware_root_mapping" not in manifest.capability_ids:
        raise T111QualificationError(
            "current source manifest lacks the T110 capability"
        )
    resolved = path.resolve(strict=True)
    reference = {
        "path": str(resolved),
        "schema_id": "sts-lightspeed-source-manifest-v1",
        "sha256": _sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
        "capabilities": list(manifest.capability_ids),
    }
    return identity, reference


def _t085_source_manifest_paths(
    restore_document: Mapping[str, object],
) -> tuple[Path, Path]:
    try:
        source_bindings = t088_canary._source_references(restore_document)
    except T088CanaryPathError as exc:
        raise T111QualificationError(
            "T085 restore evidence lacks valid source bindings"
        ) from exc
    paths: list[Path] = []
    for stratum in ("B", "C"):
        cohort = source_bindings.get(stratum)
        if not isinstance(cohort, Mapping):
            raise T111QualificationError(
                f"T085 {stratum} source-manifest binding is unavailable"
            )
        try:
            reference = t088_canary._artifact_reference(
                cohort.get("source_manifest"),
                f"T085 {stratum} source manifest",
            )
        except T088CanaryPathError as exc:
            raise T111QualificationError(
                f"T085 {stratum} source-manifest binding is unavailable"
            ) from exc
        paths.append(Path(str(reference["path"])))
    return paths[0], paths[1]


def _validate_t101_order(
    attempts: Sequence[Mapping[str, object]],
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    source_by_identity: dict[str, Mapping[str, object]] = {}
    for row in source_rows:
        identity = row.get("selection_identity")
        stratum = row.get("cohort", row.get("stratum"))
        if (
            not isinstance(identity, str)
            or not identity
            or stratum not in T101_SOURCE_COUNTS
            or identity in source_by_identity
        ):
            raise T111QualificationError(
                "qualified T087/T085 identity set is malformed"
            )
        source_by_identity[identity] = row
    if len(source_by_identity) != 413:
        raise T111QualificationError("qualified source population is not exactly 413")
    counts = Counter(str(row.get("cohort", row.get("stratum"))) for row in source_rows)
    if dict(counts) != T101_SOURCE_COUNTS:
        raise T111QualificationError("qualified source population A/B/C counts changed")
    if len(attempts) != 413:
        raise T111QualificationError("T101 attempt evidence does not contain 413 rows")

    observed: dict[str, list[Mapping[str, object]]] = {
        name: [] for name in T101_SOURCE_COUNTS
    }
    for attempt in attempts:
        identity = attempt.get("selection_identity")
        stratum = attempt.get("stratum")
        if (
            not isinstance(identity, str)
            or stratum not in T101_SOURCE_COUNTS
            or attempt.get("admitted") is not False
            or identity not in source_by_identity
            or source_by_identity[identity].get(
                "cohort", source_by_identity[identity].get("stratum")
            )
            != stratum
        ):
            raise T111QualificationError("T101 attempt/source identity binding changed")
        observed[stratum].append(attempt)

    canonical_order: list[dict[str, object]] = []
    for stratum, expected_count in T101_SOURCE_COUNTS.items():
        attempts_for_stratum = observed[stratum]
        if len(attempts_for_stratum) != expected_count:
            raise T111QualificationError("T101 attempt stratum count changed")
        expected_order = sorted(
            (
                identity
                for identity, row in source_by_identity.items()
                if row.get("cohort", row.get("stratum")) == stratum
            ),
            key=lambda identity: (
                hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                identity,
            ),
        )
        for ordinal, (identity, attempt) in enumerate(
            zip(expected_order, attempts_for_stratum, strict=True)
        ):
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            if (
                attempt.get("selection_identity") != identity
                or attempt.get("source_ordinal") != ordinal
                or attempt.get("selection_digest") != digest
            ):
                raise T111QualificationError("T101 hash-ordered source identity drift")
            canonical_order.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "source_ordinal": ordinal,
                    "selection_digest": digest,
                }
            )
    if [row.get("stratum") for row in attempts] != [
        row["stratum"] for row in canonical_order
    ] or [row.get("selection_identity") for row in attempts] != [
        row["selection_identity"] for row in canonical_order
    ]:
        raise T111QualificationError("T101 attempt list stratum/order sequence changed")
    return {
        "record_count": len(canonical_order),
        "source_counts": dict(T101_SOURCE_COUNTS),
        "ordered_identity_binding_sha256": _canonical_sha256(canonical_order),
        "historical_t101_attempt_order_exact": True,
        "attempted_count": len(attempts),
        "historical_selected_count": 0,
    }


def _write_new_json(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    path = path.resolve()
    if path.exists():
        raise T111QualificationError("refusing to overwrite retained T111 evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_json(value)
    with path.open("xb") as stream:
        stream.write(data)
    return {
        "path": str(path),
        "schema_id": value.get("schema_id"),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _write_preparation_manifest(
    *,
    implementation_head: str,
    qualification_ref: Mapping[str, object],
    preparation_ref: Mapping[str, object] | None,
    eligible: bool,
    artifact_root: Path,
) -> dict[str, object]:
    artifacts = {"input_qualification": dict(qualification_ref)}
    if preparation_ref is not None:
        artifacts["readiness_preparation"] = dict(preparation_ref)
    manifest = {
        "schema_id": T111_PREPARATION_MANIFEST_SCHEMA,
        "task_id": "T111",
        "implementation_head": implementation_head,
        "approved_spec_commit": T111_APPROVED_SPEC_COMMIT,
        "terminal_classification": (
            "READY_FOR_MAINTAINER_EXECUTION_REVIEW"
            if eligible
            else T111_INPUT_INELIGIBLE
        ),
        "candidate_execution_started": False,
        "not_an_execution_record": True,
        "artifact_references": artifacts,
        "retention_reason": (
            "Retain exact-head T111 input qualification and pre-execution readiness."
        ),
        "deletion_condition": (
            "Delete only after T111 lifecycle and provenance review has no remaining audit consumers."
        ),
    }
    return _write_new_json(artifact_root / "t111-preparation-manifest.json", manifest)


def prepare_t111_input_qualification_from_paths(
    *,
    implementation_head: str,
    t101_retention_manifest_path: Path = T111_DEFAULT_RETENTION_MANIFEST,
    artifact_root: Path,
    source_manifest_path: Path | None = None,
) -> dict[str, object]:
    """Revalidate accepted source inputs and write readiness-only artifacts."""

    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(character not in "0123456789abcdef" for character in implementation_head)
    ):
        raise T111QualificationError("T111 implementation head must be a full SHA-1")
    if source_manifest_path is None:
        source_manifest_path = default_lightspeed_source_manifest_path()
    started_head = implementation_head
    reasons: list[str] = []
    evidence: dict[str, object] = {
        "schema_id": T111_QUALIFICATION_SCHEMA,
        "task_id": "T111",
        "implementation_head": started_head,
        "approved_spec_commit": T111_APPROVED_SPEC_COMMIT,
        "python_runtime": _python_runtime_fingerprint(),
        "native_identity": None,
        "historical_t101_execution_identity": None,
        "historical_t101_artifacts": {},
        "historical_t101_source_manifest": None,
        "retained_artifacts": {},
        "source_population": None,
        "eligible": False,
        "ineligible_reasons": reasons,
        "candidate_execution_started": False,
        "terminal_classification": T111_INPUT_INELIGIBLE,
    }

    try:
        _manifest, input_admission, cohort, historical, old_native = (
            t103_particle_diagnostic._load_t101_terminal_inputs(
                t101_retention_manifest_path
            )
        )
        evidence["historical_t101_execution_identity"] = historical[
            "retained_t101_execution_identity"
        ]
        evidence["historical_t101_artifacts"] = {
            role: historical[role]
            for role in (
                "t101_terminal_retention_manifest",
                "t101_input_admission",
                "t101_cohort_admission",
                "t101_final_report",
                "t101_cost_report",
            )
        }
        evidence["historical_t101_source_artifacts"] = historical[
            "accepted_t101_source_artifacts"
        ]
        if old_native.get("commit") != "97f59b620efe5ee1571f8da298c99d1e21c1149b":
            raise T111QualificationError("historical T101 native identity changed")
    except (OSError, T103PathError, T101IncompleteError, T111QualificationError) as exc:
        reasons.append("T101_TERMINAL_EVIDENCE_UNAVAILABLE_OR_INVALID")
        evidence["failure_type"] = type(exc).__name__
        qualification_ref = _write_new_json(
            artifact_root / "t111-input-qualification.json", evidence
        )
        manifest_ref = _write_preparation_manifest(
            implementation_head=implementation_head,
            qualification_ref=qualification_ref,
            preparation_ref=None,
            eligible=False,
            artifact_root=artifact_root,
        )
        return {
            "qualification": evidence,
            "qualification_artifact": qualification_ref,
            "preparation_manifest_artifact": manifest_ref,
        }

    try:
        current_native, current_manifest_ref = _source_manifest_identity(
            source_manifest_path
        )
        evidence["native_identity"] = current_native
        evidence["current_source_manifest"] = current_manifest_ref
    except (OSError, ValueError, T111QualificationError) as exc:
        reasons.append("CURRENT_T110_SOURCE_MANIFEST_MISMATCH")
        evidence["failure_type"] = type(exc).__name__

    artifact_bindings = t103_particle_diagnostic._t101_input_artifact_bindings(
        input_admission
    )
    if evidence["native_identity"] is not None:
        try:
            gate_values = {
                "t087_formal_path": Path(artifact_bindings["t087_formal"]["path"]),
                "t087_report_path": Path(artifact_bindings["t087_report"]["path"]),
                "t087_retention_path": Path(
                    artifact_bindings["t087_retention"]["path"]
                ),
                "t085_selection_path": Path(
                    artifact_bindings["t085_selection"]["path"]
                ),
                "t085_restore_path": Path(artifact_bindings["t085_restore"]["path"]),
                "a_pool_path": Path(artifact_bindings["t085_canonical_a"]["path"]),
                "b_pool_path": Path(artifact_bindings["t085_canonical_b"]["path"]),
                "c_pool_path": Path(artifact_bindings["t085_canonical_c"]["path"]),
            }
            restore_doc_path = gate_values["t085_restore_path"]
            restore_doc = json.loads(restore_doc_path.read_text(encoding="utf-8"))
            if (
                not isinstance(restore_doc, Mapping)
                or restore_doc.get("schema_id") != T085_RESTORE_SCHEMA_ID
            ):
                raise T111QualificationError("T085 restore schema changed")
            b_manifest, c_manifest = _t085_source_manifest_paths(restore_doc)
            formal, gate, t088_inputs = (
                t088_canary._admit_t088_canary_inputs_from_paths(
                    implementation_head=implementation_head,
                    **gate_values,
                    b_source_manifest_path=b_manifest,
                    c_source_manifest_path=c_manifest,
                    historical_t085_producer_only=True,
                )
            )
            if not isinstance(gate.source_selection_manifest_identity, Mapping):
                raise T111QualificationError(
                    "T085 source selection identity is missing"
                )
            source_rows = t088_canary._project_t087_cohort(
                formal,
                gate.source_selection_manifest_identity,
                gate.canonical_records_by_cohort,
            )
            attempts = cohort.get("attempted")
            if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)):
                raise T111QualificationError(
                    "T101 candidate attempt rows are unavailable"
                )
            source_population = _validate_t101_order(attempts, source_rows)
            evidence["source_population"] = source_population
            evidence["t087_t085_input_bindings"] = t088_inputs
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            T088CanaryPathError,
            T111QualificationError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            reasons.append("T087_T085_SOURCE_POPULATION_OR_RESTORE_INELIGIBLE")
            evidence["failure_type"] = type(exc).__name__

    verified_artifacts: dict[str, object] = {}
    verified_historical_artifacts: dict[str, object] = {}
    historical_artifacts = evidence.get("historical_t101_artifacts")
    if isinstance(historical_artifacts, Mapping):
        for role, binding in historical_artifacts.items():
            try:
                if not isinstance(binding, Mapping):
                    raise T111QualificationError(
                        f"historical T101 artifact binding is malformed: {role}"
                    )
                verified_historical_artifacts[str(role)] = _verify_file_binding(
                    binding, role=str(role)
                )
            except (OSError, T111QualificationError) as exc:
                reasons.append(f"HISTORICAL_T101_ARTIFACT_INELIGIBLE:{role}")
                evidence["failure_type"] = type(exc).__name__
    evidence["verified_historical_t101_artifacts"] = verified_historical_artifacts

    old_manifest_binding = artifact_bindings.get("native_source_manifest")
    producer = historical.get("retained_t101_execution_identity", {})
    producer_commit = (
        producer.get("implementation_head") if isinstance(producer, Mapping) else None
    )
    try:
        if not isinstance(old_manifest_binding, Mapping) or not isinstance(
            producer_commit, str
        ):
            raise T111QualificationError("historical T101 manifest binding is missing")
        verified_artifacts["native_source_manifest"] = _verify_historical_manifest_blob(
            old_manifest_binding,
            producer_commit=producer_commit,
            repo_root=_git_repository_root(t101_retention_manifest_path),
        )
    except (OSError, T111QualificationError) as exc:
        reasons.append("HISTORICAL_T101_SOURCE_MANIFEST_BLOB_MISMATCH")
        evidence["failure_type"] = type(exc).__name__

    gate_references: dict[str, Mapping[str, object]] = {}
    if isinstance(evidence.get("t087_t085_input_bindings"), Mapping):
        current_refs = evidence["t087_t085_input_bindings"]
        for role in (
            "t087_formal",
            "t087_report",
            "t087_retention",
            "t085_selection",
            "t085_restore",
        ):
            ref = current_refs.get(role)
            if isinstance(ref, Mapping):
                gate_references[role] = ref
        canonical = current_refs.get("t085_canonical")
        if isinstance(canonical, Mapping):
            for stratum, suffix in (("A", "a"), ("B", "b"), ("C", "c")):
                item = canonical.get(stratum)
                ref = item.get("map") if isinstance(item, Mapping) else None
                if isinstance(ref, Mapping):
                    gate_references[f"t085_canonical_{suffix}"] = ref

    for role, binding in artifact_bindings.items():
        if role == "native_source_manifest":
            continue
        try:
            if role in gate_references:
                observed = gate_references[role]
                verified_artifacts[role] = _verify_t088_gate_reference(
                    binding, observed=observed, role=role
                )
            else:
                verified_artifacts[role] = _verify_file_binding(binding, role=role)
        except (OSError, T111QualificationError) as exc:
            reasons.append(f"RETAINED_ARTIFACT_INELIGIBLE:{role}")
            evidence["failure_type"] = type(exc).__name__

    if evidence["source_population"] is None:
        reasons.append("EXACT_413_IDENTITY_POPULATION_NOT_PROVEN")
    if evidence["native_identity"] is None:
        reasons.append("CURRENT_T110_NATIVE_IDENTITY_NOT_PROVEN")
    if len(verified_artifacts) != len(artifact_bindings):
        reasons.append("RETAINED_T101_INPUT_SET_NOT_FULLY_HASH_VERIFIED")

    evidence["retained_artifacts"] = verified_artifacts
    evidence["ineligible_reasons"] = list(dict.fromkeys(reasons))
    eligible = not reasons
    evidence["eligible"] = eligible
    evidence["terminal_classification"] = None if eligible else T111_INPUT_INELIGIBLE
    qualification_ref = _write_new_json(
        artifact_root / "t111-input-qualification.json", evidence
    )
    preparation = {
        "schema_id": T111_READINESS_PREPARATION_SCHEMA,
        "task_id": "T111",
        "preparation_only": True,
        "candidate_execution_authorized": False,
        "candidate_execution_started": False,
        "implementation_head": implementation_head,
        "approved_spec_commit": T111_APPROVED_SPEC_COMMIT,
        "python_runtime": evidence["python_runtime"],
        "input_qualification": qualification_ref,
        "input_qualification_sha256": qualification_ref["sha256"],
        "native_identity": evidence["native_identity"],
        "proposed_executor_cap": {
            "maximum_candidate_workers": 4,
            "effective_worker_count": None,
            "shard_ranges": None,
            "memory_limit_mib": None,
            "memavailable_floor_mib": None,
            "sampling_interval_seconds": None,
            "status": "PENDING_MAINTAINER_RESOURCE_REVIEW",
        },
        "next_action": (
            "Maintainer independently verifies this qualification and records "
            "the exact-head execution/resource readiness before any candidate call."
        ),
        "eligible_for_maintainer_execution_review": eligible,
    }
    preparation_ref = _write_new_json(
        artifact_root / "t111-readiness-preparation.json", preparation
    )
    manifest_ref = _write_preparation_manifest(
        implementation_head=implementation_head,
        qualification_ref=qualification_ref,
        preparation_ref=preparation_ref,
        eligible=eligible,
        artifact_root=artifact_root,
    )
    return {
        "qualification": evidence,
        "qualification_artifact": qualification_ref,
        "readiness_preparation": preparation,
        "readiness_preparation_artifact": preparation_ref,
        "preparation_manifest_artifact": manifest_ref,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-head", required=True)
    parser.add_argument(
        "--t101-retention-manifest",
        type=Path,
        default=T111_DEFAULT_RETENTION_MANIFEST,
    )
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare_t111_input_qualification_from_paths(
            implementation_head=args.implementation_head,
            t101_retention_manifest_path=args.t101_retention_manifest,
            artifact_root=args.artifact_root,
            source_manifest_path=args.source_manifest,
        )
    except (
        OSError,
        T101IncompleteError,
        T111QualificationError,
        T111ConfiguredSearchError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "INPUT_QUALIFICATION_FAILED",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": "INPUT_QUALIFIED"
                if result["qualification"]["eligible"] is True
                else T111_INPUT_INELIGIBLE,
                "qualification_artifact": result["qualification_artifact"],
                "readiness_preparation_artifact": result.get(
                    "readiness_preparation_artifact"
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if result["qualification"]["eligible"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
