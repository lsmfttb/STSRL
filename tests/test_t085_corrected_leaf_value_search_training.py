from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import sts_combat_rl.commands.t085_corrected_leaf_value_search_training as t085_command
import sts_combat_rl.t085_corrected_leaf_value_search_evaluation as t085_evaluation
import sts_combat_rl.t085_corrected_leaf_value_search_repair as t085_repair
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_ARTIFACT_ROOT,
    T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    T085_NATIVE_IDENTITY,
    T085_REQUIRED_INPUT_ARTIFACT_KEYS,
    artifact_reference,
    write_t085_json_artifact,
)


class _FakeTrainingReport:
    def __init__(self, repair_seed: int) -> None:
        self.repair_seed = repair_seed
        self.optimizer_steps = 900
        self.batch_size = 32
        self.example_count = 960

    def to_dict(self) -> dict[str, object]:
        return {
            "training_ok": True,
            "repair_seed": self.repair_seed,
            "example_count": self.example_count,
            "optimizer_steps": self.optimizer_steps,
            "batch_size": self.batch_size,
            "target_mean": 1.0,
            "target_std": 2.0,
            "batch_plan_sha256": "a" * 64,
            "initial_mse": 1.0,
            "final_mse": 0.1,
            "initial_mae": 0.8,
            "final_mae": 0.2,
            "problems": [],
        }


class _FakeTrainingConfig:
    def to_dict(self) -> dict[str, object]:
        return {
            "learning_rate": 0.001,
            "adam_betas": [0.9, 0.999],
            "adam_epsilon": 1e-8,
            "weight_decay": 0.0,
            "gradient_clip_norm": 10.0,
            "batch_size": 32,
            "optimizer_steps": 900,
        }


def _training_artifact_path(tmp_path, name: str) -> Path:
    return T085_ARTIFACT_ROOT / f".pytest-t085-training-{tmp_path.name}-{name}.json"


def test_training_command_runs_both_repair_seeds_and_writes_only_training_artifacts(
    tmp_path, monkeypatch
) -> None:
    input_paths: list[Path] = []

    def json_input(name: str, schema_id: str) -> dict[str, object]:
        path = _training_artifact_path(tmp_path, name)
        reference = write_t085_json_artifact(
            path,
            {"input": name},
            schema_id=schema_id,
        )
        input_paths.append(path)
        return reference

    collector_path = _training_artifact_path(tmp_path, "collector")
    collector_reference = write_t085_json_artifact(
        collector_path,
        {"formal_rows": []},
        schema_id="t084-native-internal-leaf-collector-v1",
    )
    input_paths.append(collector_path)
    report_reference = json_input(
        "report", "t084-search-v2-internal-leaf-target-generation-v1"
    )
    retention_path = _training_artifact_path(tmp_path, "retention")
    retention_reference = write_t085_json_artifact(
        retention_path,
        {"task_id": "T084", "outputs": {"report": report_reference}},
        schema_id="t084-retention-manifest-v1",
    )
    input_paths.append(retention_path)

    parent_paths: dict[int, Path] = {}
    parent_references: dict[int, dict[str, object]] = {}
    for seed in (85001, 85002):
        path = _training_artifact_path(tmp_path, f"parent-{seed}")
        path.write_bytes(f"parent-{seed}".encode("ascii"))
        input_paths.append(path)
        parent_paths[seed] = path
        parent_references[seed] = artifact_reference(
            path,
            schema_id="torch-policy-value-checkpoint-v1",
        )
    t052_reference = json_input("t052", "fixed-cohort-v3-jsonl")
    t042_reference = json_input("t042", "t042-assisted-source-scale-manifest-v2")
    identities = {
        "t084_report": report_reference,
        "t084_retention": retention_reference,
        "t084_formal_dataset": collector_reference,
        "t064_parent_85001": parent_references[85001],
        "t064_parent_85002": parent_references[85002],
        "t052_cohort": t052_reference,
        "t042_scale_manifest": t042_reference,
    }
    assert tuple(identities) == T085_REQUIRED_INPUT_ARTIFACT_KEYS

    examples = tuple(SimpleNamespace(index=index) for index in range(960))
    formal_dataset = SimpleNamespace(
        examples=examples,
        retention_manifest_path=str(retention_path.resolve()),
        collector_path=str(collector_path.resolve()),
        collector_sha256=collector_reference["sha256"],
        collector_byte_count=collector_reference["byte_count"],
    )
    parents = {
        seed: SimpleNamespace(
            repair_seed=seed,
            path=str(parent_paths[seed].resolve()),
            sha256=parent_references[seed]["sha256"],
            model=f"model-{seed}",
            training_data_provenance={
                "task_id": "T064",
                "trainer_input_artifact_id": f"t064-{seed}",
            },
        )
        for seed in (85001, 85002)
    }
    calls: list[dict[str, object]] = []

    def fake_resolve(path: Path):
        assert path == retention_path.resolve()
        return formal_dataset

    def fake_load(path: str | Path, *, repair_seed: int):
        assert Path(path).resolve() == parent_paths[repair_seed].resolve()
        return parents[repair_seed]

    def fake_train(parent_model, examples, **kwargs):
        calls.append(
            {
                "parent_model": parent_model,
                "examples": examples,
                **kwargs,
            }
        )
        seed = int(kwargs["repair_seed"])
        return SimpleNamespace(
            report=_FakeTrainingReport(seed),
            config=_FakeTrainingConfig(),
            training_data_provenance={
                "task_id": "T085",
                "repair_seed": seed,
                "training_input_sha256": formal_dataset.collector_sha256,
                "training_input_path": formal_dataset.collector_path,
                "training_input_byte_count": formal_dataset.collector_byte_count,
            },
            policy_target_kind="behavior_chosen_action_one_hot",
            policy_target_source="frozen_parent_checkpoint_policy_path",
            invariance_audit={
                "valid": True,
                "example_count": 960,
                "policy_mismatch_count": 0,
                "parameter_group_mismatch_counts": {
                    "policy": 0,
                    "encoder": 0,
                    "hp": 0,
                    "resource": 0,
                },
            },
        )

    saved_paths: list[Path] = []

    def fake_save(result, path: Path, *, parent_checkpoint_sha256: str) -> None:
        assert result.report.repair_seed in (85001, 85002)
        assert parent_checkpoint_sha256 == parents[result.report.repair_seed].sha256
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"checkpoint-{result.report.repair_seed}".encode("ascii"))
        saved_paths.append(path)

    monkeypatch.setattr(t085_evaluation, "T085_INPUT_ARTIFACT_IDENTITIES", identities)
    monkeypatch.setattr(
        t085_repair,
        "T085_PARENT_CHECKPOINT_PATH_BY_SEED",
        {seed: str(path) for seed, path in parent_paths.items()},
    )
    monkeypatch.setattr(t085_repair, "resolve_t084_formal_dataset", fake_resolve)
    monkeypatch.setattr(t085_repair, "load_t085_verified_parent_checkpoint", fake_load)
    monkeypatch.setattr(t085_repair, "train_t085_corrected_value_head", fake_train)
    monkeypatch.setattr(t085_repair, "save_t085_corrected_checkpoint", fake_save)
    monkeypatch.setattr(
        t085_command,
        "_current_code_identity",
        lambda: {"repository": "lsmfttb/STSRL", "ref": "HEAD", "commit": "test"},
    )

    try:
        result = t085_command.run_t085_corrected_value_head_training_from_path(
            retention_path
        )
        assert [call["repair_seed"] for call in calls] == [85001, 85002]
        assert [parent.repair_seed for parent in parents.values()] == [85001, 85002]
        for call in calls:
            assert call["examples"] is formal_dataset.examples
            assert call["training_input_path"] == formal_dataset.collector_path
            assert call["training_input_sha256"] == formal_dataset.collector_sha256
            assert (
                call["training_input_byte_count"] == formal_dataset.collector_byte_count
            )
            assert call["formal_dataset"] is formal_dataset

        eligibility_reference = result["input_eligibility_manifest"]
        eligibility = json.loads(
            Path(eligibility_reference["path"]).read_text(encoding="utf-8")
        )
        assert eligibility["schema_id"] == T085_INPUT_ELIGIBILITY_SCHEMA_ID
        assert eligibility["accepted_inputs"] == identities
        assert eligibility["native_identity"] == T085_NATIVE_IDENTITY

        assert [repair["repair_seed"] for repair in result["repairs"]] == [
            85001,
            85002,
        ]
        assert len(saved_paths) == 2
        manifest = json.loads(
            Path(result["training_manifest"]["path"]).read_text(encoding="utf-8")
        )
        assert manifest["training_completed"] is True
        assert manifest["scientific_evaluation_completed"] is False
        assert manifest["source_artifacts_generated"] is False
        assert manifest["outcome_artifacts_generated"] is False
        assert manifest["unexecuted_stages"] == [
            "native_source_generation",
            "restore_parity",
            "paired_search_evaluation",
            "terminal_classification",
        ]
    finally:
        for path in input_paths + saved_paths:
            path.unlink(missing_ok=True)
        for path in (
            T085_ARTIFACT_ROOT / "training" / "input-eligibility-manifest.json",
            T085_ARTIFACT_ROOT / "training" / "t085-training-manifest.json",
        ):
            path.unlink(missing_ok=True)
        for seed in (85001, 85002):
            (
                T085_ARTIFACT_ROOT
                / "training"
                / "reports"
                / f"t085-training-report-{seed}.json"
            ).unlink(missing_ok=True)
            (
                T085_ARTIFACT_ROOT
                / "training"
                / "checkpoints"
                / f"t085-corrected-value-head-{seed}.pt"
            ).unlink(missing_ok=True)


def test_training_command_parser_requires_exact_retention_argument() -> None:
    with pytest.raises(SystemExit):
        t085_command.build_parser().parse_args([])
    args = t085_command.build_parser().parse_args(
        ["--retention-manifest", "/accepted/t084-retention.json"]
    )
    assert args.retention_manifest == Path("/accepted/t084-retention.json")


def test_training_command_main_only_routes_to_workflow(monkeypatch, capsys) -> None:
    calls: list[Path] = []

    def fake_workflow(path: Path) -> dict[str, object]:
        calls.append(path)
        return {"task_id": "T085", "training_completed": True}

    monkeypatch.setattr(
        t085_command,
        "run_t085_corrected_value_head_training_from_path",
        fake_workflow,
    )
    retention_path = Path("/accepted/t084-retention.json")
    assert t085_command.main(["--retention-manifest", str(retention_path)]) == 0
    assert calls == [retention_path]
    assert '"training_completed": true' in capsys.readouterr().err
