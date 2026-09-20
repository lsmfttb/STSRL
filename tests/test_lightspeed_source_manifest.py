from __future__ import annotations

import json
from pathlib import Path

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
    assert manifest.integration.commit == ("97f59b620efe5ee1571f8da298c99d1e21c1149b")
    assert set(REQUIRED_NATIVE_CAPABILITY_IDS).issubset(manifest.capability_ids)
    assert "native_battle_search_root" in manifest.capability_ids
    assert "native_root_prior_allocation" in manifest.capability_ids
    assert "native_battle_search_v2_tree_internal" in manifest.capability_ids
    assert "native_battle_search_v2_progressive_bias_h1" in manifest.capability_ids
    assert "native_battle_search_v2_tree_geometry" in manifest.capability_ids
    assert "native_battle_search_v2_state_utilization" in manifest.capability_ids
    assert "native_terminal_resource_identity" in manifest.capability_ids
    assert "constructed_battle_start_transforms" in manifest.capability_ids
    assert (
        "native_t096_public_information_hidden_future_sampler"
        in manifest.capability_ids
    )
    assert "native_stsr006_particle_search_bridge" in manifest.capability_ids
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


def test_t096_native_capability_declares_sampler_boundary() -> None:
    manifest = load_lightspeed_source_manifest()
    capability = next(
        item
        for item in manifest.supported_native_capabilities
        if item.capability_id == "native_t096_public_information_hidden_future_sampler"
    )
    assert capability.task_provenance == ("T096",)
    assert "native-battle-public-information-v2" in capability.description
    assert (
        "draw-knowledge and hidden-intent mechanics remain explicitly unsupported"
        not in capability.description
    )
    assert (
        "StepSimulator.t096_public_information_projection"
        in capability.required_python_api
    )
    assert (
        "StepSimulator.t096_anchor_distribution_metadata"
        in capability.required_python_api
    )
    assert (
        "StepSimulator.sample_hidden_future_particles.particle_count"
        in capability.required_python_api
    )
    assert "StepSimulator.t096_visibility_audit" in capability.required_python_api
    assert (
        "StepSimulator.t096_visibility_audit.frozen_eye_full_order"
        in capability.required_python_api
    )
    assert (
        "StepSimulator.t096_visibility_audit.runic_dome_mixed_counter_sampler_fails_closed"
        in capability.required_python_api
    )
    assert (
        "StepSimulator.t096_visibility_audit.private_hidden_state_projection_invariant"
        in capability.required_python_api
    )


def test_t099_native_capability_declares_particle_search_boundary() -> None:
    manifest = load_lightspeed_source_manifest()
    capability = next(
        item
        for item in manifest.supported_native_capabilities
        if item.capability_id == "native_stsr006_particle_search_bridge"
    )

    assert capability.task_provenance == ("T099",)
    for required_semantic in (
        "native public-consistent sampling",
        "full_simulator_state_oracle_like",
        "full_state_continuation_strategy_fusion_proxy",
        "no cross-particle aggregation or action selection",
        "exact Q_public",
        "information-set-optimal Search",
        "exact Bayesian/deterministic-seed posterior expectation",
        "IID posterior-sampling claims",
        "incomplete or ambiguous mappings",
    ):
        assert required_semantic in capability.description
    for required_api in (
        "StepSimulator.sample_hidden_future_particles_search",
        "StepSimulator.sample_hidden_future_particles_search.particles.root_evaluation.root_action_mapping.public_action_ordinal",
        "StepSimulator.sample_hidden_future_particles_search.particles.root_evaluation.root_action_mapping.source_action",
        "StepSimulator.sample_hidden_future_particles_search.particles.root_evaluation.root_action_mapping.edge_public_occurrence_count",
        "StepSimulator.stsr006_particle_search_audit",
        "StepSimulator.stsr006_particle_search_audit.duplicate_occurrence_mapping",
        "StepSimulator.stsr006_particle_search_audit.unsupported_anchor_fails_closed",
    ):
        assert required_api in capability.required_python_api


def test_t099_canonical_source_verifier_requires_bridge_checks() -> None:
    verifier = (
        Path(__file__).parents[1] / "scripts" / "verify_lightspeed_source.sh"
    ).read_text(encoding="utf-8")

    for required_check in (
        '"sample_hidden_future_particles_search"',
        '"stsr006_particle_search_audit"',
        "validate_t099_particle_search_audit",
        "validate_t099_particle_search_bridge",
        "scripts/test_t096_particle_search_bridge.py",
        "${STSRL_LIGHTSPEED_BUILD_JOBS:-2}",
    ):
        assert required_check in verifier
    assert (
        'PYTHONPATH="$worktree/$build_dir:$repo_root/src${PYTHONPATH:+:' not in verifier
    )


def test_lightspeed_source_identity_manifest_path_is_cwd_stable(
    tmp_path, monkeypatch
) -> None:
    manifest = load_lightspeed_source_manifest()
    first_cwd = tmp_path / "worktree-a"
    second_cwd = tmp_path / "worktree-b"
    first_cwd.mkdir()
    second_cwd.mkdir()

    monkeypatch.chdir(first_cwd)
    first = lightspeed_source_identity_dict(manifest)
    monkeypatch.chdir(second_cwd)
    second = lightspeed_source_identity_dict(manifest)

    assert first == second
    assert first["manifest_path"] == "docs/sts_lightspeed_source_manifest.json"


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
