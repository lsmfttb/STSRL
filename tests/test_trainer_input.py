from __future__ import annotations

from dataclasses import replace
from io import StringIO
from pathlib import Path

import pytest

from sts_combat_rl.sim.decision_record import DECISION_RECORD_SCHEMA_VERSION
from sts_combat_rl.sim.trainer_input import (
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    dump_trainer_input_dataset_jsonl,
    load_trainer_input_dataset_jsonl_text,
)


def test_trainer_input_v1_fixture_migrates_to_current_schema() -> None:
    text = Path("tests/fixtures/trainer_input_v1_legacy.jsonl").read_text(
        encoding="utf-8"
    )

    dataset = load_trainer_input_dataset_jsonl_text(text)
    record = dataset.records[0]

    assert dataset.format_version == TRAINER_INPUT_DATASET_FORMAT_VERSION
    assert dataset.decision_record_schema_version == DECISION_RECORD_SCHEMA_VERSION
    assert dataset.migration_report.source_version == 1
    assert (
        dataset.migration_report.target_version == TRAINER_INPUT_DATASET_FORMAT_VERSION
    )
    assert dataset.migration_report.applied_versions == (
        TRAINER_INPUT_DATASET_FORMAT_VERSION,
    )
    assert "v1 omitted per-decision controller provenance" in (
        dataset.migration_report.losses
    )
    assert record.controller_provenance == {}
    assert record.source_metadata["source_kind"] == "unknown"
    assert record.legal_action_identities[0]["action_id"] is None
    assert record.legal_action_identities[1]["occurrence"] == 1
    assert record.chosen_action_identity == record.legal_action_identities[1]
    assert any("controller provenance is missing" in item for item in dataset.problems)


def test_trainer_input_writer_rejects_non_current_schema() -> None:
    text = Path("tests/fixtures/trainer_input_v1_legacy.jsonl").read_text(
        encoding="utf-8"
    )
    current = load_trainer_input_dataset_jsonl_text(text)
    legacy = replace(current, format_version=1)

    with pytest.raises(ValueError, match="only emits current format version"):
        dump_trainer_input_dataset_jsonl(legacy, StringIO())
