from __future__ import annotations

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.sim.trainer_input import trainer_input_dataset_to_jsonl_text

from t009_helpers import make_trainer_dataset


def test_cli_trainer_input_preflight_reports_gate(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "trainer.jsonl"
    dataset_path.write_text(
        trainer_input_dataset_to_jsonl_text(make_trainer_dataset([(20, 1), (20, 1)])),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--trainer-input-preflight",
                str(dataset_path),
                "--pytorch-gate-required-acts",
                "1",
                "--pytorch-gate-min-records",
                "2",
                "--pytorch-gate-min-sources",
                "2",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Trainer input preflight summary" in captured.err
    assert "T009 broad training gate" in captured.err
    assert "broad training allowed: yes" in captured.err


def test_cli_pytorch_search_guidance_train_writes_checkpoint(
    tmp_path,
    capsys,
) -> None:
    pytest.importorskip("torch")
    dataset_path = tmp_path / "trainer.jsonl"
    checkpoint_path = tmp_path / "policy_value.pt"
    dataset_path.write_text(
        trainer_input_dataset_to_jsonl_text(make_trainer_dataset([(20, 1), (20, 1)])),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--pytorch-search-guidance-train",
                str(dataset_path),
                "--pytorch-checkpoint-output",
                str(checkpoint_path),
                "--pytorch-gate-override",
                "smoke",
                "--pytorch-epochs",
                "1",
                "--pytorch-hidden-size",
                "8",
                "--pytorch-batch-size",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert checkpoint_path.exists()
    assert "checkpoint written: yes" in captured.err
    assert "raw policy diagnostic final" in captured.err
    assert "search-guided fixed evaluation: not_run" in captured.err
