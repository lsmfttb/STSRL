from __future__ import annotations

import json

import pytest

from sts_combat_rl.sim.lightspeed_source import (
    LIGHTSPEED_SOURCE_MANIFEST_SCHEMA_ID,
    REQUIRED_NATIVE_CAPABILITY_IDS,
    default_lightspeed_source_manifest_path,
    format_lightspeed_source_identity,
    lightspeed_source_identity_dict,
    load_lightspeed_source_manifest,
    parse_lightspeed_source_manifest,
)


def _default_manifest_payload() -> dict[str, object]:
    return json.loads(
        default_lightspeed_source_manifest_path().read_text(encoding="utf-8")
    )


def test_default_lightspeed_source_manifest_names_pinned_integration() -> None:
    manifest = load_lightspeed_source_manifest()

    assert manifest.schema_id == LIGHTSPEED_SOURCE_MANIFEST_SCHEMA_ID
    assert manifest.manifest_version == 1
    assert manifest.upstream.repository_url == (
        "https://github.com/gamerpuppy/sts_lightspeed.git"
    )
    assert manifest.upstream.base_commit == ("7476a81954020087da31d41d16fddf475746ec2d")
    assert manifest.integration.repository_url == (
        "https://github.com/lsmfttb/sts_lightspeed.git"
    )
    assert manifest.integration.branch == "stsrl/main"
    assert manifest.integration.ref == "refs/heads/stsrl/main"
    assert manifest.integration.commit == ("9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a")
    assert set(REQUIRED_NATIVE_CAPABILITY_IDS).issubset(manifest.capability_ids)
    assert "native_battle_search_root" in manifest.capability_ids
    assert "native_root_prior_allocation" in manifest.capability_ids
    assert "native_terminal_resource_identity" in manifest.capability_ids
    assert "constructed_battle_start_transforms" in manifest.capability_ids
    assert manifest.legacy_patch_stack.status == "retired_provenance"


def test_lightspeed_source_identity_is_json_safe_and_reportable() -> None:
    manifest = load_lightspeed_source_manifest()

    identity = lightspeed_source_identity_dict(manifest)
    json.dumps(identity, sort_keys=True)
    text = format_lightspeed_source_identity(identity)

    assert identity["manifest_schema_id"] == LIGHTSPEED_SOURCE_MANIFEST_SCHEMA_ID
    assert identity["integration_commit"] == manifest.integration.commit
    assert "sts_lightspeed source identity" in text
    assert manifest.integration.commit in text
    assert "canonical verifier: scripts/verify_lightspeed_source.sh" in text


def test_lightspeed_source_manifest_missing_file_fails(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="source manifest not found"):
        load_lightspeed_source_manifest(tmp_path / "missing.json")


def test_lightspeed_source_manifest_requires_integration_commit() -> None:
    payload = _default_manifest_payload()
    integration = dict(payload["integration"])  # type: ignore[index]
    integration.pop("commit")
    payload["integration"] = integration

    with pytest.raises(ValueError, match="integration.commit"):
        parse_lightspeed_source_manifest(payload)


def test_lightspeed_source_manifest_rejects_wrong_commit_shape() -> None:
    payload = _default_manifest_payload()
    integration = dict(payload["integration"])  # type: ignore[index]
    integration["commit"] = "820a2f8"
    payload["integration"] = integration

    with pytest.raises(ValueError, match="40-character lowercase git commit"):
        parse_lightspeed_source_manifest(payload)


def test_lightspeed_source_manifest_requires_ref_to_match_branch() -> None:
    payload = _default_manifest_payload()
    integration = dict(payload["integration"])  # type: ignore[index]
    integration["ref"] = "refs/heads/other"
    payload["integration"] = integration

    with pytest.raises(ValueError, match="ref must match"):
        parse_lightspeed_source_manifest(payload)


def test_lightspeed_source_manifest_requires_current_capability_inventory() -> None:
    payload = _default_manifest_payload()
    capabilities = list(payload["supported_native_capabilities"])  # type: ignore[index]
    payload["supported_native_capabilities"] = [
        item for item in capabilities if item["id"] != "native_root_prior_allocation"
    ]

    with pytest.raises(ValueError, match="native_root_prior_allocation"):
        parse_lightspeed_source_manifest(payload)
