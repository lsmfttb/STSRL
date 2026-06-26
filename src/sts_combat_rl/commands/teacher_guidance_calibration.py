"""Command helpers for the T027 teacher-guidance calibration report."""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path
from typing import Sequence

from sts_combat_rl.sim.teacher_guidance_calibration import (
    DEFAULT_CALIBRATION_TOP_K,
    TeacherGuidanceCalibrationReport,
    build_teacher_guidance_calibration_report,
    dump_teacher_guidance_calibration_report_json,
    format_teacher_guidance_calibration_report,
)
from sts_combat_rl.sim.trainer_input import load_trainer_input_dataset_jsonl


def run_teacher_guidance_calibration_from_paths(
    *,
    trainer_input_path: Path,
    checkpoint_paths: Sequence[Path],
    output_path: Path | None = None,
    top_k: int = DEFAULT_CALIBRATION_TOP_K,
) -> TeacherGuidanceCalibrationReport:
    """Load trainer input and checkpoints, then build the T027 report."""

    trainer_bytes = trainer_input_path.read_bytes()
    trainer_sha256 = hashlib.sha256(trainer_bytes).hexdigest()
    dataset = load_trainer_input_dataset_jsonl(StringIO(trainer_bytes.decode("utf-8")))

    from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueGuidanceScorer

    scorers = [
        TorchPolicyValueGuidanceScorer.from_checkpoint_path(path)
        for path in checkpoint_paths
    ]
    report = build_teacher_guidance_calibration_report(
        dataset,
        scorers,
        trainer_input_artifact_identity={
            "path": str(trainer_input_path),
            "sha256": trainer_sha256,
            "artifact_id": f"trainer-input-sha256:{trainer_sha256}",
            "byte_count": len(trainer_bytes),
        },
        top_k=top_k,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_teacher_guidance_calibration_report_json(report, stream)
    return report


def format_teacher_guidance_calibration_command(
    report: TeacherGuidanceCalibrationReport,
    *,
    detail_limit: int = 5,
) -> str:
    """Format the path-level T027 command report."""

    return format_teacher_guidance_calibration_report(
        report,
        detail_limit=detail_limit,
    )
