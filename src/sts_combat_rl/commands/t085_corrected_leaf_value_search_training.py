"""Run the bounded, offline T085 value-head-only training workflow.

This command resolves only the accepted T084 retention/formal collector and
the two qualified T064 parents, then delegates training and checkpoint
validation to the repair module.  It writes training artifacts under the
stable T085 root.  Native source generation, restored evaluation, and outcome
artifacts remain outside this command and are never synthesized here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import sts_combat_rl.t085_corrected_leaf_value_search_evaluation as t085_evaluation
import sts_combat_rl.t085_corrected_leaf_value_search_repair as t085_repair

T085_TRAINING_REPORT_SCHEMA_ID = "t085-corrected-value-training-report-v1"
T085_TRAINING_MANIFEST_SCHEMA_ID = "t085-corrected-value-training-manifest-v1"
T085_PARENT_KEY_BY_SEED = {
    85001: "t064_parent_85001",
    85002: "t064_parent_85002",
}


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _current_code_identity() -> dict[str, object]:
    repository = Path(__file__).resolve().parents[3]
    try:
        process = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot resolve the STSRL implementation commit") from exc
    commit = process.stdout.strip()
    if not commit:
        raise ValueError("STSRL implementation commit is empty")
    return {
        "repository": "lsmfttb/STSRL",
        "ref": "HEAD",
        "commit": commit,
    }


def _exact_input_reference(
    key: str,
    *,
    verified_path: str | Path | None = None,
    verified_sha256: str | None = None,
    verified_byte_count: int | None = None,
) -> dict[str, object]:
    expected = t085_evaluation.T085_INPUT_ARTIFACT_IDENTITIES.get(key)
    if not isinstance(expected, Mapping):
        raise ValueError(f"T085 accepted input identity is missing for {key}")
    expected_path = Path(_required_string(expected.get("path"), f"{key}.path"))
    try:
        expected_path = expected_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"accepted T085 input is unavailable: {key}") from exc
    actual_path = (
        expected_path if verified_path is None else Path(verified_path).resolve()
    )
    if actual_path != expected_path:
        raise ValueError(f"accepted T085 input path mismatch for {key}")
    if not actual_path.is_file():
        raise ValueError(f"accepted T085 input is unavailable: {key}")
    actual_byte_count = actual_path.stat().st_size
    expected_byte_count = expected.get("byte_count")
    if actual_byte_count != expected_byte_count:
        raise ValueError(f"accepted T085 input size mismatch for {key}")
    if verified_byte_count is not None and verified_byte_count != actual_byte_count:
        raise ValueError(f"verified T085 input size mismatch for {key}")
    actual_sha256 = (
        verified_sha256
        if verified_sha256 is not None
        else t085_repair.sha256_file(actual_path)
    )
    if actual_sha256 != expected.get("sha256"):
        raise ValueError(f"accepted T085 input SHA-256 mismatch for {key}")
    return dict(expected)


def _accepted_t084_input_references(
    retention_manifest_path: Path,
    formal_dataset: t085_repair.T085FormalDataset,
    parents: Mapping[int, t085_repair.T085VerifiedParentCheckpoint],
) -> dict[str, dict[str, object]]:
    retention_reference = _exact_input_reference(
        "t084_retention", verified_path=retention_manifest_path
    )
    retention = _read_json(retention_manifest_path)
    outputs = _required_mapping(retention.get("outputs"), "T084 outputs")
    report = _required_mapping(outputs.get("report"), "T084 report")
    report_path = Path(_required_string(report.get("path"), "T084 report.path"))
    report_reference = _exact_input_reference("t084_report", verified_path=report_path)
    collector_reference = _exact_input_reference(
        "t084_formal_dataset",
        verified_path=formal_dataset.collector_path,
        verified_sha256=formal_dataset.collector_sha256,
        verified_byte_count=formal_dataset.collector_byte_count,
    )
    references = {
        "t084_report": report_reference,
        "t084_retention": retention_reference,
        "t084_formal_dataset": collector_reference,
    }
    for seed, key in T085_PARENT_KEY_BY_SEED.items():
        parent = parents.get(seed)
        if parent is None:
            raise ValueError(f"T085 verified parent is missing for {seed}")
        references[key] = _exact_input_reference(
            key,
            verified_path=parent.path,
            verified_sha256=parent.sha256,
        )
    for key in ("t052_cohort", "t042_scale_manifest"):
        references[key] = _exact_input_reference(key)
    if set(references) != set(t085_evaluation.T085_REQUIRED_INPUT_ARTIFACT_KEYS):
        raise ValueError("T085 accepted input identity set is incomplete")
    return references


def _read_json(path: Path) -> Mapping[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON artifact: {path}") from exc
    return _required_mapping(document, str(path))


def _training_paths(repair_seed: int) -> tuple[Path, Path]:
    root = t085_repair.T085_ARTIFACT_ROOT.resolve()
    return (
        root
        / "training"
        / "checkpoints"
        / f"t085-corrected-value-head-{repair_seed}.pt",
        root / "training" / "reports" / f"t085-training-report-{repair_seed}.json",
    )


def run_t085_corrected_value_head_training_from_path(
    retention_manifest_path: Path,
) -> dict[str, object]:
    """Resolve accepted inputs, train both repairs, and retain only training artifacts."""

    retention_manifest_path = retention_manifest_path.resolve(strict=True)
    formal_dataset = t085_repair.resolve_t084_formal_dataset(retention_manifest_path)
    if (
        Path(formal_dataset.retention_manifest_path).resolve()
        != retention_manifest_path
    ):
        raise ValueError("resolved T084 dataset is not bound to the retention manifest")
    if len(formal_dataset.examples) != t085_repair.T085_FORMAL_ROW_COUNT:
        raise ValueError("T085 training requires exactly 960 resolved formal rows")
    parents: dict[int, t085_repair.T085VerifiedParentCheckpoint] = {}
    for repair_seed in t085_repair.T085_REPAIR_SEEDS:
        parents[repair_seed] = t085_repair.load_t085_verified_parent_checkpoint(
            t085_repair.T085_PARENT_CHECKPOINT_PATH_BY_SEED[repair_seed],
            repair_seed=repair_seed,
        )
    input_references = _accepted_t084_input_references(
        retention_manifest_path, formal_dataset, parents
    )
    code_identity = _current_code_identity()
    input_eligibility_payload = {
        "schema_id": t085_evaluation.T085_INPUT_ELIGIBILITY_SCHEMA_ID,
        "task_id": "T085",
        "accepted_inputs": input_references,
        "code_identity": code_identity,
        "native_identity": dict(t085_evaluation.T085_NATIVE_IDENTITY),
        "training_scope": {
            "formal_row_count": len(formal_dataset.examples),
            "collector_path": formal_dataset.collector_path,
            "collector_sha256": formal_dataset.collector_sha256,
            "collector_byte_count": formal_dataset.collector_byte_count,
            "repair_seeds": list(t085_repair.T085_REPAIR_SEEDS),
            "optimizer_steps": t085_repair.T085_OPTIMIZER_STEPS,
        },
    }

    input_eligibility_path = (
        t085_repair.T085_ARTIFACT_ROOT / "training" / "input-eligibility-manifest.json"
    )
    input_eligibility_reference = t085_evaluation.write_t085_json_artifact(
        input_eligibility_path,
        input_eligibility_payload,
        schema_id=t085_evaluation.T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    )

    results: dict[int, t085_repair.T085TrainingResult] = {}
    for repair_seed in t085_repair.T085_REPAIR_SEEDS:
        parent = parents[repair_seed]
        results[repair_seed] = t085_repair.train_t085_corrected_value_head(
            parent.model,
            formal_dataset.examples,
            repair_seed=repair_seed,
            parent_checkpoint_sha256=parent.sha256,
            training_input_sha256=formal_dataset.collector_sha256,
            training_input_path=formal_dataset.collector_path,
            training_input_byte_count=formal_dataset.collector_byte_count,
            parent_guidance_provenance=parent.training_data_provenance,
            formal_dataset=formal_dataset,
            parent_checkpoint_path=parent.path,
        )

    repairs: list[dict[str, object]] = []
    for repair_seed in t085_repair.T085_REPAIR_SEEDS:
        parent = parents[repair_seed]
        result = results[repair_seed]
        checkpoint_path, report_path = _training_paths(repair_seed)
        t085_repair.save_t085_corrected_checkpoint(
            result,
            checkpoint_path,
            parent_checkpoint_sha256=parent.sha256,
        )
        checkpoint_reference = t085_evaluation.artifact_reference(
            checkpoint_path,
            schema_id=t085_repair.TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
        )
        report_payload = {
            "schema_id": T085_TRAINING_REPORT_SCHEMA_ID,
            "task_id": "T085",
            "repair_seed": repair_seed,
            "checkpoint": checkpoint_reference,
            "input_eligibility_manifest": input_eligibility_reference,
            "parent": {
                "path": parent.path,
                "sha256": parent.sha256,
                "repair_seed": repair_seed,
            },
            "training_report": result.report.to_dict(),
            "training_config": result.config.to_dict(),
            "training_data_provenance": result.training_data_provenance,
            "policy_target_kind": result.policy_target_kind,
            "policy_target_source": result.policy_target_source,
            "invariance_audit": result.invariance_audit,
            "source_artifacts_generated": False,
            "outcome_artifacts_generated": False,
            "scientific_evaluation_completed": False,
        }
        report_reference = t085_evaluation.write_t085_json_artifact(
            report_path,
            report_payload,
            schema_id=T085_TRAINING_REPORT_SCHEMA_ID,
        )
        repairs.append(
            {
                "repair_seed": repair_seed,
                "parent_checkpoint": {
                    "path": parent.path,
                    "sha256": parent.sha256,
                },
                "checkpoint": checkpoint_reference,
                "training_report": report_reference,
            }
        )

    training_manifest_path = (
        t085_repair.T085_ARTIFACT_ROOT / "training" / "t085-training-manifest.json"
    )
    training_manifest = {
        "schema_id": T085_TRAINING_MANIFEST_SCHEMA_ID,
        "task_id": "T085",
        "training_completed": True,
        "scientific_evaluation_completed": False,
        "source_artifacts_generated": False,
        "outcome_artifacts_generated": False,
        "input_eligibility_manifest": input_eligibility_reference,
        "accepted_t084_retention_manifest": input_references["t084_retention"],
        "formal_dataset": {
            "row_count": len(formal_dataset.examples),
            "path": formal_dataset.collector_path,
            "sha256": formal_dataset.collector_sha256,
            "byte_count": formal_dataset.collector_byte_count,
        },
        "repair_seeds": list(t085_repair.T085_REPAIR_SEEDS),
        "optimizer_steps": t085_repair.T085_OPTIMIZER_STEPS,
        "training_config": results[85001].config.to_dict(),
        "repairs": repairs,
        "code_identity": code_identity,
        "native_identity": dict(t085_evaluation.T085_NATIVE_IDENTITY),
        "unexecuted_stages": [
            "native_source_generation",
            "restore_parity",
            "paired_search_evaluation",
            "terminal_classification",
        ],
    }
    training_manifest_reference = t085_evaluation.write_t085_json_artifact(
        training_manifest_path,
        training_manifest,
        schema_id=T085_TRAINING_MANIFEST_SCHEMA_ID,
    )
    return {
        "task_id": "T085",
        "training_manifest": training_manifest_reference,
        "input_eligibility_manifest": input_eligibility_reference,
        "repairs": repairs,
        "source_artifacts_generated": False,
        "outcome_artifacts_generated": False,
        "scientific_evaluation_completed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retention-manifest",
        type=Path,
        required=True,
        help="Exact accepted T084 retention manifest used to resolve formal rows.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_t085_corrected_value_head_training_from_path(
            args.retention_manifest
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"T085 training command failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, default=str), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T085_PARENT_KEY_BY_SEED",
    "T085_TRAINING_MANIFEST_SCHEMA_ID",
    "T085_TRAINING_REPORT_SCHEMA_ID",
    "build_parser",
    "main",
    "run_t085_corrected_value_head_training_from_path",
]
