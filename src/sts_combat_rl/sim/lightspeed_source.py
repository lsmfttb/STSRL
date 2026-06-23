"""Pinned external ``sts_lightspeed`` source identity helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


LIGHTSPEED_SOURCE_MANIFEST_SCHEMA_ID = "sts-lightspeed-source-manifest-v1"
LIGHTSPEED_SOURCE_MANIFEST_VERSION = 1
LIGHTSPEED_SOURCE_MANIFEST_FILENAME = "sts_lightspeed_source_manifest.json"
REQUIRED_NATIVE_CAPABILITY_IDS = (
    "step_simulation",
    "checkpoint_capture_restore",
    "battle_start_metadata",
    "run_potion_snapshot",
    "non_combat_potion_actions",
    "gcc15_build_compatibility",
    "native_public_projection",
    "native_battle_search_root",
)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class UpstreamSource:
    """The unmodified upstream source identity that STSRL integrates from."""

    repository_url: str
    base_commit: str


@dataclass(frozen=True)
class IntegrationSource:
    """The pinned external integration source used for STSRL builds."""

    repository_url: str
    branch: str
    ref: str
    commit: str


@dataclass(frozen=True)
class PythonModuleSpec:
    """The pybind module expected after building the pinned source."""

    name: str
    simulator_class: str


@dataclass(frozen=True)
class BuildSpec:
    """Build settings the source verifier applies in a disposable worktree."""

    cmake_policy_version_minimum: str
    cmake_target: str
    build_directory: str
    submodules: tuple[str, ...]


@dataclass(frozen=True)
class NativeProjectionContract:
    """Native raw public-projection labels retained for compatibility audits."""

    schema_id: str
    external_base_commit_label: str
    patch_identity: str


@dataclass(frozen=True)
class NativeCapability:
    """One native capability required by current STSRL main."""

    capability_id: str
    description: str
    task_provenance: tuple[str, ...]
    required_python_api: tuple[str, ...]


@dataclass(frozen=True)
class LegacyPatchStackDisposition:
    """How the old ordered patch stack is retained after source integration."""

    status: str
    verifier_script: str
    patches: tuple[str, ...]


@dataclass(frozen=True)
class LightSpeedSourceManifest:
    """Versioned repository-owned manifest for the external simulator source."""

    path: Path
    schema_id: str
    manifest_version: int
    upstream: UpstreamSource
    integration: IntegrationSource
    python_module: PythonModuleSpec
    build: BuildSpec
    native_projection_contract: NativeProjectionContract
    supported_native_capabilities: tuple[NativeCapability, ...]
    legacy_patch_stack: LegacyPatchStackDisposition

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(
            capability.capability_id
            for capability in self.supported_native_capabilities
        )


def default_lightspeed_source_manifest_path() -> Path:
    """Return the repository-owned source manifest path."""

    module_root = Path(__file__).resolve().parents[3]
    candidate = module_root / "docs" / LIGHTSPEED_SOURCE_MANIFEST_FILENAME
    if candidate.exists():
        return candidate
    cwd_candidate = Path.cwd() / "docs" / LIGHTSPEED_SOURCE_MANIFEST_FILENAME
    return cwd_candidate


def load_lightspeed_source_manifest(
    path: str | Path | None = None,
) -> LightSpeedSourceManifest:
    """Load and validate the pinned ``sts_lightspeed`` source manifest."""

    manifest_path = (
        Path(path) if path is not None else default_lightspeed_source_manifest_path()
    )
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"sts_lightspeed source manifest not found: {manifest_path}"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"sts_lightspeed source manifest is invalid JSON: {exc.msg}"
        ) from exc
    return parse_lightspeed_source_manifest(raw, path=manifest_path)


def parse_lightspeed_source_manifest(
    raw: object,
    *,
    path: str | Path = LIGHTSPEED_SOURCE_MANIFEST_FILENAME,
) -> LightSpeedSourceManifest:
    """Validate one source-manifest payload."""

    manifest_path = Path(path)
    payload = _mapping(raw, "source manifest")
    schema_id = _required_string(payload, "schema_id", "source manifest")
    if schema_id != LIGHTSPEED_SOURCE_MANIFEST_SCHEMA_ID:
        raise ValueError(f"unsupported source manifest schema_id: {schema_id!r}")
    manifest_version = _required_int(payload, "manifest_version", "source manifest")
    if manifest_version != LIGHTSPEED_SOURCE_MANIFEST_VERSION:
        raise ValueError(f"unsupported source manifest version: {manifest_version!r}")

    upstream = _parse_upstream(
        _required_mapping(payload, "upstream", "source manifest")
    )
    integration = _parse_integration(
        _required_mapping(payload, "integration", "source manifest")
    )
    python_module = _parse_python_module(
        _required_mapping(payload, "python_module", "source manifest")
    )
    build = _parse_build(_required_mapping(payload, "build", "source manifest"))
    native_projection_contract = _parse_native_projection_contract(
        _required_mapping(payload, "native_projection_contract", "source manifest")
    )
    capabilities = _parse_capabilities(
        _required_sequence(payload, "supported_native_capabilities", "source manifest")
    )
    legacy_patch_stack = _parse_legacy_patch_stack(
        _required_mapping(payload, "legacy_patch_stack", "source manifest")
    )

    capability_ids = [capability.capability_id for capability in capabilities]
    missing = [
        capability_id
        for capability_id in REQUIRED_NATIVE_CAPABILITY_IDS
        if capability_id not in capability_ids
    ]
    if missing:
        raise ValueError(
            "source manifest is missing required native capabilities: "
            + ", ".join(missing)
        )
    if len(set(capability_ids)) != len(capability_ids):
        raise ValueError("source manifest contains duplicate native capability ids")

    return LightSpeedSourceManifest(
        path=manifest_path,
        schema_id=schema_id,
        manifest_version=manifest_version,
        upstream=upstream,
        integration=integration,
        python_module=python_module,
        build=build,
        native_projection_contract=native_projection_contract,
        supported_native_capabilities=tuple(capabilities),
        legacy_patch_stack=legacy_patch_stack,
    )


def lightspeed_source_identity_dict(
    manifest: LightSpeedSourceManifest | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe identity block for reports and provenance."""

    source = manifest if manifest is not None else load_lightspeed_source_manifest()
    return {
        "manifest_schema_id": source.schema_id,
        "manifest_version": source.manifest_version,
        "manifest_path": _display_path(source.path),
        "upstream_repository_url": source.upstream.repository_url,
        "upstream_base_commit": source.upstream.base_commit,
        "integration_repository_url": source.integration.repository_url,
        "integration_branch": source.integration.branch,
        "integration_ref": source.integration.ref,
        "integration_commit": source.integration.commit,
        "python_module": source.python_module.name,
        "simulator_class": source.python_module.simulator_class,
        "native_capabilities": list(source.capability_ids),
        "legacy_patch_stack_status": source.legacy_patch_stack.status,
        "canonical_verifier": "scripts/verify_lightspeed_source.sh",
    }


def format_lightspeed_source_identity(
    identity: Mapping[str, Any] | LightSpeedSourceManifest | None = None,
) -> str:
    """Format source identity lines for WSL gate output."""

    if isinstance(identity, LightSpeedSourceManifest):
        values = lightspeed_source_identity_dict(identity)
    elif identity is None:
        values = lightspeed_source_identity_dict()
    else:
        values = dict(identity)
    capabilities = values.get("native_capabilities", [])
    capability_text = (
        ", ".join(str(item) for item in capabilities)
        if isinstance(capabilities, Sequence) and not isinstance(capabilities, str)
        else str(capabilities)
    )
    return "\n".join(
        [
            "sts_lightspeed source identity",
            (
                "manifest: "
                f"{values.get('manifest_schema_id')} "
                f"v{values.get('manifest_version')} "
                f"({values.get('manifest_path')})"
            ),
            (
                "upstream: "
                f"{values.get('upstream_repository_url')} "
                f"@ {values.get('upstream_base_commit')}"
            ),
            (
                "integration: "
                f"{values.get('integration_repository_url')} "
                f"{values.get('integration_ref')} "
                f"@ {values.get('integration_commit')}"
            ),
            (
                "python module: "
                f"{values.get('python_module')}.{values.get('simulator_class')}"
            ),
            f"native capabilities: {capability_text}",
            f"legacy patch stack: {values.get('legacy_patch_stack_status')}",
            f"canonical verifier: {values.get('canonical_verifier')}",
        ]
    )


def _parse_upstream(data: Mapping[str, Any]) -> UpstreamSource:
    return UpstreamSource(
        repository_url=_required_string(data, "repository_url", "upstream"),
        base_commit=_required_commit(data, "base_commit", "upstream"),
    )


def _parse_integration(data: Mapping[str, Any]) -> IntegrationSource:
    branch = _required_string(data, "branch", "integration")
    ref = _required_string(data, "ref", "integration")
    if ref != f"refs/heads/{branch}":
        raise ValueError("integration ref must match integration branch")
    return IntegrationSource(
        repository_url=_required_string(data, "repository_url", "integration"),
        branch=branch,
        ref=ref,
        commit=_required_commit(data, "commit", "integration"),
    )


def _parse_python_module(data: Mapping[str, Any]) -> PythonModuleSpec:
    return PythonModuleSpec(
        name=_required_string(data, "name", "python_module"),
        simulator_class=_required_string(data, "simulator_class", "python_module"),
    )


def _parse_build(data: Mapping[str, Any]) -> BuildSpec:
    return BuildSpec(
        cmake_policy_version_minimum=_required_string(
            data, "cmake_policy_version_minimum", "build"
        ),
        cmake_target=_required_string(data, "cmake_target", "build"),
        build_directory=_required_string(data, "build_directory", "build"),
        submodules=tuple(
            _required_string(item, str(index), "build.submodules")
            for index, item in enumerate(
                _required_sequence(data, "submodules", "build")
            )
        ),
    )


def _parse_native_projection_contract(
    data: Mapping[str, Any],
) -> NativeProjectionContract:
    return NativeProjectionContract(
        schema_id=_required_string(data, "schema_id", "native_projection_contract"),
        external_base_commit_label=_required_string(
            data, "external_base_commit_label", "native_projection_contract"
        ),
        patch_identity=_required_string(
            data, "patch_identity", "native_projection_contract"
        ),
    )


def _parse_capabilities(values: Sequence[object]) -> list[NativeCapability]:
    capabilities: list[NativeCapability] = []
    for index, value in enumerate(values):
        data = _mapping(value, f"native capability {index}")
        capability_id = _required_string(data, "id", f"native capability {index}")
        capabilities.append(
            NativeCapability(
                capability_id=capability_id,
                description=_required_string(
                    data, "description", f"native capability {capability_id}"
                ),
                task_provenance=tuple(
                    _required_string(item, str(item_index), "task_provenance")
                    for item_index, item in enumerate(
                        _required_sequence(
                            data,
                            "task_provenance",
                            f"native capability {capability_id}",
                        )
                    )
                ),
                required_python_api=tuple(
                    _required_string(item, str(item_index), "required_python_api")
                    for item_index, item in enumerate(
                        _required_sequence(
                            data,
                            "required_python_api",
                            f"native capability {capability_id}",
                        )
                    )
                ),
            )
        )
    return capabilities


def _parse_legacy_patch_stack(
    data: Mapping[str, Any],
) -> LegacyPatchStackDisposition:
    status = _required_string(data, "status", "legacy_patch_stack")
    if status != "retired_provenance":
        raise ValueError("legacy patch stack status must be retired_provenance")
    return LegacyPatchStackDisposition(
        status=status,
        verifier_script=_required_string(data, "verifier_script", "legacy_patch_stack"),
        patches=tuple(
            _required_string(item, str(index), "legacy_patch_stack.patches")
            for index, item in enumerate(
                _required_sequence(data, "patches", "legacy_patch_stack")
            )
        ),
    )


def _required_mapping(
    data: Mapping[str, Any],
    key: str,
    label: str,
) -> Mapping[str, Any]:
    return _mapping(data.get(key), f"{label}.{key}")


def _required_sequence(
    data: Mapping[str, Any],
    key: str,
    label: str,
) -> Sequence[object]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label}.{key} must be a list")
    if not value:
        raise ValueError(f"{label}.{key} must not be empty")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(value: object, key: str, label: str) -> str:
    if isinstance(value, Mapping):
        raw = value.get(key)
        field_label = f"{label}.{key}"
    else:
        raw = value
        field_label = f"{label}[{key}]"
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{field_label} must be a non-empty string")
    return raw


def _required_int(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label}.{key} must be an integer")
    return value


def _required_commit(data: Mapping[str, Any], key: str, label: str) -> str:
    value = _required_string(data, key, label)
    if not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label}.{key} must be a 40-character lowercase git commit")
    return value


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
