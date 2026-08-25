from types import SimpleNamespace

import pytest

from sts_combat_rl.sim.source_identity import (
    COMPLETE_SOURCE_IDENTITY_SCHEMA_ID,
    action_trace_identity_sha256,
    complete_source_identity,
)


def _record(*, trace_identity=None):
    metadata = {"assistance_level": "", "source_arm": ""}
    if trace_identity is not None:
        metadata["action_trace_identity"] = trace_identity
    return SimpleNamespace(
        structural_metadata=metadata,
        action_trace=[{"stable_id": "card:strike", "occurrence": 0}],
        source_checkpoint_id="checkpoint-1",
        source_seed=7,
        source_run_id="run-1",
        source_battle_index=2,
        distribution_kind="natural_run",
        checkpoint_information_regime="full_simulator_state_oracle_like",
    )


def test_complete_source_identity_preserves_occurrence_safe_trace() -> None:
    record = _record()
    identity = complete_source_identity(record)

    assert identity["schema_id"] == COMPLETE_SOURCE_IDENTITY_SCHEMA_ID
    assert identity["action_trace_identity"] == action_trace_identity_sha256(record)
    assert len(identity["complete_identity_sha256"]) == 64


def test_complete_source_identity_rejects_missing_public_provenance() -> None:
    record = _record()
    record.structural_metadata = None

    with pytest.raises(ValueError, match="structural_metadata"):
        complete_source_identity(record)


def test_action_trace_identity_rejects_duplicate_without_occurrence() -> None:
    record = _record()
    record.action_trace = [{"stable_id": "card:strike", "occurrence": True}]

    with pytest.raises(ValueError, match="occurrence"):
        action_trace_identity_sha256(record)
