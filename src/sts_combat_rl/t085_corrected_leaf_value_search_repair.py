"""T085 corrected Search v2 leaf-value training and provenance surface.

This module owns the small, offline value-head-only binding required by T085.
It consumes the explicitly retained T084 collector through its retention
manifest, copies only public model inputs into training examples, and leaves
all policy/encoder/HP/resource parameters frozen. It does not run a
simulator, generate cohorts, or perform a Search evaluation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import torch.nn.functional as F

from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND,
)
from sts_combat_rl.sim.torch_policy_value import (
    IDENTITY_VOCABULARY_VERSION,
    PUBLIC_CONTEXT_FEATURE_NAMES,
    RESOURCE_TARGET_NAMES,
    RESOURCE_TARGET_SCALES,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
    TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
    TORCH_POLICY_VALUE_MODEL_CLASS,
    PolicyValueNetwork,
    TorchPolicyValueTrainingConfig,
)
from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    _iter_collector_fields,
    validate_leaf_row,
)

T085_TASK_ID = "T085"
T085_FORMAL_ROW_COUNT = 960
T085_BATCH_SIZE = 32
T085_OPTIMIZER_STEPS = 900
T085_TARGET_KIND = SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND
T085_REPAIR_SEEDS = (85001, 85002)
T085_PARENT_CHECKPOINT_SHA256_BY_SEED = {
    85001: "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193",
    85002: "32dbf18a187e8b6d465bb026d90643e3dd28624066628019c61455fcd8f5573a",
}
T085_FORMAL_DATASET_SCHEMA_ID = "t084-native-internal-leaf-collector-v1"
T085_RETENTION_SCHEMA_ID = "t084-retention-manifest-v1"
T085_RETENTION_SHA256 = (
    "754a9d2560fb5b01c53e7789bdd558e5ef3cc9d0eca4dd690f8f1ab8df1fb0f6"
)
T085_REPORT_SHA256 = "b6cbcb5ee96d9538adb6ee7a4849a138f6d3a3f93b6127e7ba0ff91dcae1ad1c"
T085_COLLECTOR_SHA256 = (
    "f17cd7f33c11048d59a80a49f0197a972e636bbd36e25fd3ce9849f05d600d91"
)
T085_REPORT_SCHEMA_ID = "t084-search-v2-internal-leaf-target-generation-v1"
T085_T084_CLASSIFICATION = "LEAF_CONTINUATION_UTILITY_TARGETS_READY"
T085_DE_NORMALIZATION = "z_pred * target_std + target_mean"
T085_NATIVE_UTILITY_UNITS = "BattleScumSearcher2.evaluateEndState"


@dataclass(frozen=True)
class T085LeafValueExample:
    """Compact public input and target extracted from one formal T084 row."""

    state_features: tuple[float, ...]
    legal_action_features: tuple[tuple[float, ...], ...]
    eligible_action_indices: tuple[int, ...]
    native_utility: float
    exact_leaf_identity: str
    sampling_arm: str
    act: int


@dataclass(frozen=True)
class T085FormalDataset:
    """Materialized public-only view of the explicitly retained formal rows."""

    examples: tuple[T085LeafValueExample, ...]
    retention_manifest_path: str
    collector_path: str
    collector_sha256: str


@dataclass(frozen=True)
class T085TrainingConfig:
    """The exact T085 optimizer binding; there is no tunable search surface."""

    learning_rate: float = 0.001
    adam_betas: tuple[float, float] = (0.9, 0.999)
    adam_epsilon: float = 1e-8
    weight_decay: float = 0.0
    gradient_clip_norm: float = 10.0
    batch_size: int = T085_BATCH_SIZE
    optimizer_steps: int = T085_OPTIMIZER_STEPS

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


T085_DEFAULT_TRAINING_CONFIG = T085TrainingConfig()


@dataclass(frozen=True)
class T085TrainingReport:
    training_ok: bool
    example_count: int
    repair_seed: int
    target_mean: float
    target_std: float
    optimizer_steps: int
    batch_size: int
    batch_plan_sha256: str
    initial_mse: float
    final_mse: float
    initial_mae: float
    final_mae: float
    problems: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class T085TrainingResult:
    model: PolicyValueNetwork
    report: T085TrainingReport
    config: T085TrainingConfig
    training_data_provenance: dict[str, object]
    policy_target_kind: str
    policy_target_source: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _formal_example(row: Mapping[str, object]) -> T085LeafValueExample:
    validated = validate_leaf_row(row, require_replicates=100)
    public = _required_mapping(validated["public_model_input"], "public_model_input")
    state_raw = public.get("state_features")
    actions_raw = public.get("legal_action_features")
    eligible_raw = public.get("eligible_action_indices")
    if not isinstance(state_raw, Sequence) or isinstance(state_raw, (str, bytes)):
        raise ValueError("T084 public state features are malformed")
    if not isinstance(actions_raw, Sequence) or isinstance(actions_raw, (str, bytes)):
        raise ValueError("T084 public action features are malformed")
    if not isinstance(eligible_raw, Sequence) or isinstance(eligible_raw, (str, bytes)):
        raise ValueError("T084 eligible action indices are malformed")
    state = tuple(_finite_float(value, "state feature") for value in state_raw)
    actions = tuple(
        tuple(_finite_float(value, "action feature") for value in action)
        for action in actions_raw
    )
    eligible = tuple(eligible_raw)
    if any(isinstance(index, bool) or not isinstance(index, int) for index in eligible):
        raise ValueError("T084 eligible action indices must be integers")
    if not eligible or any(index < 0 or index >= len(actions) for index in eligible):
        raise ValueError("T084 eligible action indices are invalid")
    public_hash = validated.get("public_model_input_sha256")
    if public_hash is not None and public_hash != _canonical_sha256(public):
        raise ValueError("T084 public model input hash mismatch")
    return T085LeafValueExample(
        state_features=state,
        legal_action_features=actions,
        eligible_action_indices=eligible,
        native_utility=_finite_float(validated.get("target_mean"), "target_mean"),
        exact_leaf_identity=_required_string(
            validated.get("exact_leaf_identity"), "exact_leaf_identity"
        ),
        sampling_arm=_required_string(validated.get("sampling_arm"), "sampling_arm"),
        act=validated["act"],  # type: ignore[arg-type]
    )


def resolve_t084_formal_dataset(
    retention_manifest_path: str | Path,
    *,
    verify_collector_hash: bool = True,
) -> T085FormalDataset:
    """Resolve formal rows only through the accepted T084 retention manifest."""

    retention_path = Path(retention_manifest_path)
    if sha256_file(retention_path) != T085_RETENTION_SHA256:
        raise ValueError("T084 retention manifest SHA-256 is not the accepted identity")
    retention = json.loads(retention_path.read_text(encoding="utf-8"))
    if not isinstance(retention, Mapping):
        raise ValueError("T084 retention manifest is malformed")
    if retention.get("schema_id") != T085_RETENTION_SCHEMA_ID:
        raise ValueError("T084 retention manifest schema is unsupported")
    if retention.get("task_id") != "T084":
        raise ValueError("T084 retention manifest task identity is invalid")
    outputs = _required_mapping(retention.get("outputs"), "T084 outputs")
    formal = _required_mapping(
        outputs.get("formal_target_dataset"), "T084 formal target dataset"
    )
    if (
        formal.get("available") is not True
        or formal.get("schema_id") != T085_FORMAL_DATASET_SCHEMA_ID
        or formal.get("json_pointer") != "/formal_rows"
        or formal.get("sha256") != T085_COLLECTOR_SHA256
    ):
        raise ValueError("T084 formal target dataset identity is invalid")
    collector_path = Path(_required_string(formal.get("path"), "formal.path"))
    if not collector_path.is_file():
        raise ValueError("T084 formal target collector is unavailable")
    if verify_collector_hash and sha256_file(collector_path) != T085_COLLECTOR_SHA256:
        raise ValueError(
            "T084 formal target collector SHA-256 is not the accepted identity"
        )

    report_ref = _required_mapping(outputs.get("report"), "T084 report")
    if (
        report_ref.get("schema_id") != T085_REPORT_SCHEMA_ID
        or report_ref.get("sha256") != T085_REPORT_SHA256
    ):
        raise ValueError("T084 report identity is invalid")
    report_path = Path(_required_string(report_ref.get("path"), "report.path"))
    if not report_path.is_file() or sha256_file(report_path) != T085_REPORT_SHA256:
        raise ValueError("accepted T084 report is unavailable or changed")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, Mapping):
        raise ValueError("accepted T084 report is malformed")
    formal_summary = _required_mapping(report.get("formal_dataset"), "formal_dataset")
    if (
        report.get("classification") != T085_T084_CLASSIFICATION
        or formal_summary.get("row_count") != T085_FORMAL_ROW_COUNT
        or formal_summary.get("valid") is not True
        or formal_summary.get("all_replicates_valid") is not True
        or formal_summary.get("arm_counts")
        != {
            "unguided_search_v2": 320,
            "prior_only_static_64001": 320,
            "prior_only_static_64002": 320,
        }
        or formal_summary.get("act_counts") != {"1": 534, "2": 426}
    ):
        raise ValueError("accepted T084 formal dataset qualification is invalid")
    calibration = _required_mapping(report.get("calibration"), "calibration")
    if calibration.get("selected_repetition_count") != 100:
        raise ValueError("T084 selected repetition count is not 100")

    examples: list[T085LeafValueExample] = []
    fields = _iter_collector_fields(collector_path)
    for key, value in fields:
        if key == "formal_rows":
            if not isinstance(value, Iterator):
                raise ValueError("T084 formal_rows is not an array")
            for row in value:
                if not isinstance(row, Mapping):
                    raise ValueError("T084 formal row is malformed")
                examples.append(_formal_example(row))
        elif isinstance(value, Iterator):
            for _ in value:
                pass
    if len(examples) != T085_FORMAL_ROW_COUNT:
        raise ValueError("T084 formal row count is not exactly 960")
    if len({example.exact_leaf_identity for example in examples}) != len(examples):
        raise ValueError("T084 formal leaf identities are not unique")
    expected_arms = {
        "unguided_search_v2": 320,
        "prior_only_static_64001": 320,
        "prior_only_static_64002": 320,
    }
    if Counter(example.sampling_arm for example in examples) != Counter(expected_arms):
        raise ValueError("T084 formal arm counts do not match the accepted report")
    if Counter(str(example.act) for example in examples) != Counter(
        {"1": 534, "2": 426}
    ):
        raise ValueError("T084 formal Act counts do not match the accepted report")
    return T085FormalDataset(
        examples=tuple(examples),
        retention_manifest_path=str(retention_path),
        collector_path=str(collector_path),
        collector_sha256=T085_COLLECTOR_SHA256,
    )


def build_t085_batch_plan(
    record_count: int = T085_FORMAL_ROW_COUNT,
    *,
    repair_seed: int,
    config: T085TrainingConfig = T085_DEFAULT_TRAINING_CONFIG,
) -> tuple[tuple[int, ...], ...]:
    """Create the deterministic 900-step schedule required by T085."""

    if repair_seed not in T085_REPAIR_SEEDS:
        raise ValueError("T085 repair seed must be 85001 or 85002")
    if record_count != T085_FORMAL_ROW_COUNT:
        raise ValueError("T085 training requires exactly 960 formal rows")
    if (
        config.batch_size != T085_BATCH_SIZE
        or config.optimizer_steps != T085_OPTIMIZER_STEPS
    ):
        raise ValueError("T085 optimizer budget is fixed at batch 32 and 900 steps")
    if record_count % config.batch_size:
        raise ValueError("T085 record count must divide evenly into batches")
    batches_per_epoch = record_count // config.batch_size
    rng = random.Random(repair_seed)
    plan: list[tuple[int, ...]] = []
    for step in range(config.optimizer_steps):
        if step % batches_per_epoch == 0:
            indices = list(range(record_count))
            rng.shuffle(indices)
        offset = (step % batches_per_epoch) * config.batch_size
        plan.append(tuple(indices[offset : offset + config.batch_size]))
    return tuple(plan)


def _target_statistics(examples: Sequence[T085LeafValueExample]) -> tuple[float, float]:
    labels = [example.native_utility for example in examples]
    if not labels:
        raise ValueError("T085 target dataset is empty")
    mean = math.fsum(labels) / len(labels)
    variance = math.fsum((label - mean) ** 2 for label in labels) / len(labels)
    std = math.sqrt(variance)
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 0.0:
        raise ValueError("T085 target statistics are non-finite or non-positive")
    return mean, std


def _reset_outcome_head(model: PolicyValueNetwork, seed: int) -> None:
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        for module in model.outcome_head.modules():
            reset = getattr(module, "reset_parameters", None)
            if callable(reset):
                reset()


def _outcome_z_predictions(
    model: PolicyValueNetwork,
    states: torch.Tensor,
) -> torch.Tensor:
    with torch.no_grad():
        normalized = (states - model.state_mean) / model.state_std
        embedding = model.state_encoder(normalized)
    return model.outcome_head(embedding).squeeze(-1)


def _diagnostic_metrics(
    model: PolicyValueNetwork,
    examples: Sequence[T085LeafValueExample],
    target_mean: float,
    target_std: float,
) -> tuple[float, float]:
    states = torch.tensor(
        [example.state_features for example in examples], dtype=torch.float32
    )
    labels = torch.tensor(
        [(example.native_utility - target_mean) / target_std for example in examples],
        dtype=torch.float32,
    )
    with torch.no_grad():
        predictions = _outcome_z_predictions(model, states)
        residual = predictions - labels
    return float(torch.mean(residual.square())), float(torch.mean(residual.abs()))


def _validate_parent_guidance_provenance(
    value: object,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("parent guidance provenance must be a mapping")
    if value.get("task_id") == T085_TASK_ID:
        raise ValueError("parent guidance provenance must be the historical parent")
    for key in (
        "trainer_input_artifact_id",
        "trainer_input_sha256",
        "target_source_summary",
        "information_regime_counts",
        "source_information_regime_counts",
    ):
        if key not in value:
            raise ValueError(f"parent guidance provenance is missing {key}")


def train_t085_corrected_value_head(
    parent_model: PolicyValueNetwork,
    examples: Sequence[T085LeafValueExample],
    *,
    repair_seed: int,
    parent_checkpoint_sha256: str,
    training_input_sha256: str,
    training_input_path: str,
    training_input_byte_count: int,
    parent_guidance_provenance: Mapping[str, object],
    policy_target_kind: str = "behavior_chosen_action_one_hot",
    policy_target_source: str = "frozen_parent_checkpoint_policy_path",
    config: T085TrainingConfig = T085_DEFAULT_TRAINING_CONFIG,
) -> T085TrainingResult:
    """Train exactly the corrected outcome head from the qualified T084 rows."""

    if len(examples) != T085_FORMAL_ROW_COUNT:
        raise ValueError("T085 training requires exactly 960 formal rows")
    if repair_seed not in T085_REPAIR_SEEDS:
        raise ValueError("T085 repair seed must be 85001 or 85002")
    if not _is_sha256(parent_checkpoint_sha256):
        raise ValueError("parent checkpoint identity must be a SHA-256 digest")
    if parent_checkpoint_sha256 != T085_PARENT_CHECKPOINT_SHA256_BY_SEED[repair_seed]:
        raise ValueError("T085 repair seed does not match its accepted parent")
    if not _is_sha256(training_input_sha256):
        raise ValueError("training input identity must be a SHA-256 digest")
    if training_input_sha256 != T085_COLLECTOR_SHA256:
        raise ValueError("T085 training input is not the accepted T084 collector")
    if training_input_byte_count <= 0:
        raise ValueError("training input byte count must be positive")
    _validate_parent_guidance_provenance(parent_guidance_provenance)
    if parent_model.hidden_size != 16:
        raise ValueError("T085 requires the accepted hidden-size-16 parent model")
    if config != T085TrainingConfig():
        raise ValueError("T085 optimizer config is fixed and cannot be tuned")
    target_mean, target_std = _target_statistics(examples)
    batch_plan = build_t085_batch_plan(repair_seed=repair_seed, config=config)
    batch_plan_sha256 = _canonical_sha256([list(batch) for batch in batch_plan])
    model = copy.deepcopy(parent_model).cpu()
    _reset_outcome_head(model, repair_seed)
    for name, parameter in model.named_parameters():
        parameter.requires_grad = name.startswith("outcome_head.")
    optimizer = torch.optim.Adam(
        model.outcome_head.parameters(),
        lr=config.learning_rate,
        betas=config.adam_betas,
        eps=config.adam_epsilon,
        weight_decay=config.weight_decay,
    )
    initial_mse, initial_mae = _diagnostic_metrics(
        model, examples, target_mean, target_std
    )
    states = torch.tensor(
        [example.state_features for example in examples], dtype=torch.float32
    )
    labels = torch.tensor(
        [(example.native_utility - target_mean) / target_std for example in examples],
        dtype=torch.float32,
    )
    model.train()
    for batch in batch_plan:
        optimizer.zero_grad(set_to_none=True)
        batch_states = states[list(batch)]
        batch_labels = labels[list(batch)]
        predictions = _outcome_z_predictions(model, batch_states)
        loss = F.mse_loss(predictions, batch_labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.outcome_head.parameters(), config.gradient_clip_norm
        )
        optimizer.step()
    model.eval()
    final_mse, final_mae = _diagnostic_metrics(model, examples, target_mean, target_std)
    report = T085TrainingReport(
        training_ok=all(math.isfinite(value) for value in (final_mse, final_mae)),
        example_count=len(examples),
        repair_seed=repair_seed,
        target_mean=target_mean,
        target_std=target_std,
        optimizer_steps=config.optimizer_steps,
        batch_size=config.batch_size,
        batch_plan_sha256=batch_plan_sha256,
        initial_mse=initial_mse,
        final_mse=final_mse,
        initial_mae=initial_mae,
        final_mae=final_mae,
    )
    provenance: dict[str, object] = {
        "task_id": T085_TASK_ID,
        "training_input_artifact_id": f"t084-formal-dataset-sha256:{training_input_sha256}",
        "training_input_sha256": training_input_sha256,
        "training_input_path": training_input_path,
        "training_input_byte_count": training_input_byte_count,
        "training_record_count": len(examples),
        "target_kind": T085_TARGET_KIND,
        "target_source": "T084 formal post-first-action internal-leaf native utility",
        "parent_checkpoint_sha256": parent_checkpoint_sha256,
        "repair_seed": repair_seed,
        "optimizer_steps": config.optimizer_steps,
        "batch_size": config.batch_size,
        "target_mean": target_mean,
        "target_std": target_std,
        "batch_plan_sha256": batch_plan_sha256,
        "policy_target_kind": policy_target_kind,
        "policy_target_source": policy_target_source,
        "parent_guidance_provenance": dict(parent_guidance_provenance),
    }
    return T085TrainingResult(
        model=model,
        report=report,
        config=config,
        training_data_provenance=provenance,
        policy_target_kind=policy_target_kind,
        policy_target_source=policy_target_source,
    )


def audit_t085_policy_invariance(
    parent_model: PolicyValueNetwork,
    repaired_model: PolicyValueNetwork,
    examples: Sequence[T085LeafValueExample],
) -> dict[str, object]:
    """Prove non-value tensors and public policy outputs stayed unchanged."""

    parent_state = parent_model.state_dict()
    repaired_state = repaired_model.state_dict()
    problems: list[str] = []
    non_outcome_keys = sorted(
        key for key in parent_state if not key.startswith("outcome_head.")
    )
    if set(parent_state) != set(repaired_state):
        problems.append("model state-dict keys changed")
    mismatched_tensors = [
        key
        for key in non_outcome_keys
        if key not in repaired_state
        or parent_state[key].dtype != repaired_state[key].dtype
        or parent_state[key].shape != repaired_state[key].shape
        or parent_state[key].detach().cpu().contiguous().numpy().tobytes()
        != repaired_state[key].detach().cpu().contiguous().numpy().tobytes()
    ]
    if mismatched_tensors:
        problems.append("non-outcome tensors changed: " + ", ".join(mismatched_tensors))
    policy_mismatches = 0
    with torch.no_grad():
        for example in examples:
            state = torch.tensor(example.state_features, dtype=torch.float32)
            actions = torch.tensor(example.legal_action_features, dtype=torch.float32)
            parent_logits = parent_model(state, actions)[0]
            repaired_logits = repaired_model(state, actions)[0]
            indices = list(example.eligible_action_indices)
            parent_probs = torch.softmax(parent_logits[indices], dim=0)
            repaired_probs = torch.softmax(repaired_logits[indices], dim=0)
            if not torch.equal(parent_logits, repaired_logits) or not torch.equal(
                parent_probs, repaired_probs
            ):
                policy_mismatches += 1
    if policy_mismatches:
        problems.append(f"policy outputs changed on {policy_mismatches} public inputs")
    return {
        "schema_id": "t085-policy-invariance-audit-v1",
        "example_count": len(examples),
        "non_outcome_tensor_count": len(non_outcome_keys),
        "policy_mismatch_count": policy_mismatches,
        "valid": not problems,
        "problems": problems,
    }


def native_leaf_utility_from_prediction(
    predicted_z: float,
    *,
    target_mean: float,
    target_std: float,
) -> float:
    """De-normalize one corrected prediction exactly once at the boundary."""

    predicted = _finite_float(predicted_z, "predicted normalized utility")
    mean = _finite_float(target_mean, "target_mean")
    std = _finite_float(target_std, "target_std")
    if std <= 0.0:
        raise ValueError("target_std must be positive")
    value = predicted * std + mean
    if not math.isfinite(value):
        raise ValueError("native leaf utility is not finite")
    return value


def save_t085_corrected_checkpoint(
    result: T085TrainingResult,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    metadata: Mapping[str, object] | None = None,
) -> None:
    """Write a current checkpoint with an explicit T085 native-utility gate."""

    if not result.report.training_ok:
        raise ValueError("refusing to save a failed T085 checkpoint")
    if not _is_sha256(parent_checkpoint_sha256):
        raise ValueError("parent checkpoint identity must be a SHA-256 digest")
    if result.report.repair_seed not in T085_REPAIR_SEEDS:
        raise ValueError("T085 repair seed must be 85001 or 85002")
    if (
        parent_checkpoint_sha256
        != T085_PARENT_CHECKPOINT_SHA256_BY_SEED[result.report.repair_seed]
    ):
        raise ValueError("T085 repair seed does not match its accepted parent")
    if result.model.hidden_size != 16:
        raise ValueError("T085 requires the accepted hidden-size-16 parent model")
    if result.report.example_count != T085_FORMAL_ROW_COUNT:
        raise ValueError("T085 checkpoint must contain exactly 960 formal labels")
    if (
        result.training_data_provenance.get("parent_checkpoint_sha256")
        != parent_checkpoint_sha256
    ):
        raise ValueError(
            "parent checkpoint identity does not match training provenance"
        )
    target_metadata = {
        "task_id": T085_TASK_ID,
        "target_kind": T085_TARGET_KIND,
        "native_utility_units": T085_NATIVE_UTILITY_UNITS,
        "de_normalization": T085_DE_NORMALIZATION,
        "target_mean": result.report.target_mean,
        "target_std": result.report.target_std,
        "label_count": result.report.example_count,
        "parent_checkpoint_sha256": parent_checkpoint_sha256,
        "repair_seed": result.report.repair_seed,
        "optimizer_steps": result.report.optimizer_steps,
        "batch_size": result.report.batch_size,
        "batch_plan_sha256": result.report.batch_plan_sha256,
    }
    merged_metadata = dict(metadata or {})
    # Caller metadata may add provenance, but cannot weaken the semantic gate.
    merged_metadata.update(
        {
            "task_id": T085_TASK_ID,
            "outcome_target_kind": T085_TARGET_KIND,
            "t085_value_target": target_metadata,
        }
    )
    model = result.model
    payload = {
        "schema_id": TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
        "format_version": TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
        "model_class": TORCH_POLICY_VALUE_MODEL_CLASS,
        "state_feature_size": model.state_feature_size,
        "snapshot_feature_size": model.snapshot_feature_size,
        "public_context_feature_size": model.public_context_feature_size,
        "action_feature_size": model.action_feature_size,
        "hidden_size": model.hidden_size,
        "tactical_feature_schema_id": model.tactical_feature_schema_id,
        "tactical_feature_schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
        "identity_vocabulary_version": IDENTITY_VOCABULARY_VERSION,
        "public_context_feature_schema_id": model.public_context_feature_schema_id,
        "public_context_feature_schema_version": model.public_context_feature_schema_version,
        "public_context_feature_names": list(PUBLIC_CONTEXT_FEATURE_NAMES),
        "resource_target_names": list(RESOURCE_TARGET_NAMES),
        "resource_target_scales": list(RESOURCE_TARGET_SCALES),
        "policy_target_kind": result.policy_target_kind,
        "outcome_target_kind": T085_TARGET_KIND,
        "hp_target_kind": "terminal_absolute_current_hp",
        "structured_resource_target_kind": "structured_terminal_resource_components_v1",
        "model_state_dict": model.state_dict(),
        "training_config": TorchPolicyValueTrainingConfig(
            epochs=30,
            learning_rate=0.001,
            hidden_size=model.hidden_size,
            batch_size=T085_BATCH_SIZE,
            seed=result.report.repair_seed,
            adam_betas=(0.9, 0.999),
            adam_epsilon=1e-8,
            weight_decay=0.0,
            gradient_clip_norm=10.0,
        ).to_dict(),
        "training_report": result.report.to_dict(),
        "training_data_provenance": dict(result.training_data_provenance),
        "metadata": merged_metadata,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, str(path))


__all__ = [
    "T085_BATCH_SIZE",
    "T085_COLLECTOR_SHA256",
    "T085_FORMAL_ROW_COUNT",
    "T085FormalDataset",
    "T085LeafValueExample",
    "T085TrainingConfig",
    "T085TrainingReport",
    "T085TrainingResult",
    "audit_t085_policy_invariance",
    "build_t085_batch_plan",
    "native_leaf_utility_from_prediction",
    "resolve_t084_formal_dataset",
    "save_t085_corrected_checkpoint",
    "sha256_file",
    "train_t085_corrected_value_head",
]
