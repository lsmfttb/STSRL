"""Optional PyTorch policy/value model for public battle data.

This module is intentionally imported only by train-specific code.  It consumes
current trainer input records, including sanitized public run context summaries,
and predicts policy, battle-survival, terminal absolute HP, and structured
resource heads without collapsing resources into a permanent scalar reward.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
import hashlib
import math
from pathlib import Path
import random
from time import perf_counter
from typing import Any

import torch
import torch.nn.functional as F
from torch import Tensor, nn

from sts_combat_rl.sim.artifact_versioning import ArtifactMigrationReport
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.model_input import ModelInputBatch
from sts_combat_rl.sim.model_scoring import DEFAULT_ACTION_KIND_SCORE_PRIOR
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.public_context_artifacts import PUBLIC_CONTEXT_AVAILABLE
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
    encode_public_context_model_input,
    public_context_features as shared_public_context_features,
)
from sts_combat_rl.sim.resource_outcome import BATTLE_RESOURCE_OUTCOME_AVAILABLE
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceValuePrediction,
    validate_search_guidance_context,
)
from sts_combat_rl.sim.trainer_input import (
    POLICY_TARGET_KIND_BEHAVIOR,
    POLICY_TARGET_KINDS,
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    TrainerInputDataset,
    TrainerInputRecord,
)
from sts_combat_rl.sim.training_gate import (
    TRAINING_GATE_OVERRIDE_NONE,
    TrainingGateReport,
    TrainingScaleGateConfig,
    build_training_gate_report,
)


TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID = "torch-policy-value-checkpoint-v1"
TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION = 1
TORCH_POLICY_VALUE_MODEL_CLASS = "PublicBattlePolicyValueNetwork"
PUBLIC_CONTEXT_FEATURE_SCHEMA_ID = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
PUBLIC_CONTEXT_FEATURE_NAMES = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES
PUBLIC_CONTEXT_FEATURE_SIZE = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
OUTCOME_TARGET_KIND = "terminal_battle_survival_probability"
HP_TARGET_KIND = "terminal_absolute_current_hp"
STRUCTURED_RESOURCE_TARGET_KIND = "structured_terminal_resource_components_v1"
SEARCH_GUIDED_FIXED_EVAL_STATUS_NOT_RUN = "not_run"
SEARCH_GUIDED_FIXED_EVAL_REASON = (
    "model-guided search fixed evaluation is not implemented by T009; "
    "raw policy diagnostics are reported separately and are not promotion evidence"
)

RESOURCE_TARGET_NAMES = (
    "terminal_max_hp",
    "terminal_gold",
    "terminal_non_empty_potion_slots",
    "terminal_deck_size",
    "terminal_curse_count",
    "terminal_relic_count",
    "terminal_blue_key",
    "terminal_green_key",
    "terminal_red_key",
)
RESOURCE_TARGET_SCALES = (
    100.0,
    999.0,
    5.0,
    120.0,
    10.0,
    60.0,
    1.0,
    1.0,
    1.0,
)


@dataclass(frozen=True)
class TorchPolicyValueTrainingConfig:
    """Small supervised warmup configuration for search guidance."""

    epochs: int = 10
    learning_rate: float = 0.001
    hidden_size: int = 128
    hp_loss_scale: float = 100.0
    policy_loss_weight: float = 1.0
    outcome_loss_weight: float = 1.0
    hp_loss_weight: float = 1.0
    resource_loss_weight: float = 1.0
    batch_size: int = 32
    seed: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TorchPolicyValueEpochStats:
    epoch: int
    average_total_loss: float
    average_policy_loss: float
    average_outcome_loss: float
    average_hp_loss: float
    average_resource_loss: float


@dataclass(frozen=True)
class TorchPolicyValueEvaluation:
    """Raw model diagnostic metrics, separate from search-guided evaluation."""

    example_count: int
    average_total_loss: float
    average_policy_loss: float
    average_outcome_loss: float
    average_hp_loss: float
    average_resource_loss: float
    policy_top1_agreement: int
    outcome_mean_absolute_error: float
    hp_mean_absolute_error: float
    resource_target_record_count: int
    resource_mean_absolute_errors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TorchPolicyValueTrainingReport:
    """Training and raw diagnostic summary for one checkpoint."""

    training_ok: bool
    example_count: int
    state_feature_size: int
    snapshot_feature_size: int
    action_feature_size: int
    public_context_feature_size: int
    parameter_count: int
    config: TorchPolicyValueTrainingConfig
    initial_evaluation: TorchPolicyValueEvaluation
    final_evaluation: TorchPolicyValueEvaluation
    gate_report: TrainingGateReport
    policy_target_kind: str = POLICY_TARGET_KIND_BEHAVIOR
    outcome_target_kind: str = OUTCOME_TARGET_KIND
    hp_target_kind: str = HP_TARGET_KIND
    structured_resource_target_kind: str = STRUCTURED_RESOURCE_TARGET_KIND
    tactical_feature_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID
    tactical_feature_schema_version: int = TACTICAL_FEATURE_SCHEMA_VERSION
    identity_vocabulary_version: str = IDENTITY_VOCABULARY_VERSION
    public_context_feature_schema_id: str = PUBLIC_CONTEXT_FEATURE_SCHEMA_ID
    public_context_feature_schema_version: int = PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION
    public_context_feature_names: tuple[str, ...] = PUBLIC_CONTEXT_FEATURE_NAMES
    search_guided_fixed_evaluation_status: str = SEARCH_GUIDED_FIXED_EVAL_STATUS_NOT_RUN
    search_guided_fixed_evaluation_reason: str = SEARCH_GUIDED_FIXED_EVAL_REASON
    epochs: tuple[TorchPolicyValueEpochStats, ...] = ()
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class TorchPolicyValueTrainingResult:
    model: "PolicyValueNetwork"
    report: TorchPolicyValueTrainingReport


@dataclass(frozen=True)
class LoadedTorchPolicyValueCheckpoint:
    model: "PolicyValueNetwork"
    config: TorchPolicyValueTrainingConfig
    metadata: dict[str, Any] = field(default_factory=dict)
    training_data_provenance: dict[str, Any] = field(default_factory=dict)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
            target_version=TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
        )
    )


class PolicyValueNetwork(nn.Module):
    """State-action policy scorer plus independent outcome/resource heads."""

    def __init__(
        self,
        state_feature_size: int,
        action_feature_size: int,
        *,
        snapshot_feature_size: int,
        public_context_feature_size: int = PUBLIC_CONTEXT_FEATURE_SIZE,
        hidden_size: int = 128,
        tactical_feature_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID,
        public_context_feature_schema_id: str = PUBLIC_CONTEXT_FEATURE_SCHEMA_ID,
        public_context_feature_schema_version: int = (
            PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION
        ),
        public_context_feature_names: tuple[str, ...] = PUBLIC_CONTEXT_FEATURE_NAMES,
        resource_target_names: tuple[str, ...] = RESOURCE_TARGET_NAMES,
        state_mean: Tensor | None = None,
        state_std: Tensor | None = None,
        action_mean: Tensor | None = None,
        action_std: Tensor | None = None,
    ) -> None:
        super().__init__()
        if min(state_feature_size, action_feature_size, hidden_size) <= 0:
            raise ValueError("policy/value network dimensions must be positive")
        if snapshot_feature_size <= 0 or public_context_feature_size <= 0:
            raise ValueError(
                "snapshot and public-context feature sizes must be positive"
            )
        if state_feature_size != snapshot_feature_size + public_context_feature_size:
            raise ValueError(
                "state feature size must include snapshot plus public context"
            )
        if not tactical_feature_schema_id:
            raise ValueError("tactical feature schema id must be non-empty")
        if not public_context_feature_schema_id:
            raise ValueError("public context feature schema id must be non-empty")
        if public_context_feature_schema_version <= 0:
            raise ValueError("public context feature schema version must be positive")
        if len(public_context_feature_names) != public_context_feature_size:
            raise ValueError(
                "public context feature names must match public-context feature size"
            )
        if not resource_target_names:
            raise ValueError("resource target names must be non-empty")

        self.state_feature_size = int(state_feature_size)
        self.snapshot_feature_size = int(snapshot_feature_size)
        self.public_context_feature_size = int(public_context_feature_size)
        self.action_feature_size = int(action_feature_size)
        self.hidden_size = int(hidden_size)
        self.tactical_feature_schema_id = tactical_feature_schema_id
        self.public_context_feature_schema_id = public_context_feature_schema_id
        self.public_context_feature_schema_version = int(
            public_context_feature_schema_version
        )
        self.public_context_feature_names = tuple(public_context_feature_names)
        self.resource_target_names = tuple(resource_target_names)

        self.state_encoder = nn.Sequential(
            nn.Linear(state_feature_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(action_feature_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_size * 3, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )
        self.outcome_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )
        self.hp_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
            nn.Softplus(),
        )
        self.resource_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, len(self.resource_target_names)),
            nn.Softplus(),
        )
        self.register_buffer(
            "state_mean",
            _normalizer_value(state_mean, state_feature_size, fill=0.0),
        )
        self.register_buffer(
            "state_std",
            _normalizer_value(state_std, state_feature_size, fill=1.0),
        )
        self.register_buffer(
            "action_mean",
            _normalizer_value(action_mean, action_feature_size, fill=0.0),
        )
        self.register_buffer(
            "action_std",
            _normalizer_value(action_std, action_feature_size, fill=1.0),
        )

    def forward(
        self,
        state_features: Tensor,
        action_features: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        if state_features.ndim == 1:
            state_features = state_features.unsqueeze(0)
        normalized_state = (state_features - self.state_mean) / self.state_std
        normalized_actions = (action_features - self.action_mean) / self.action_std
        state_embedding = self.state_encoder(normalized_state)
        action_embedding = self.action_encoder(normalized_actions)
        expanded_state = state_embedding.expand(action_embedding.shape[0], -1)
        policy_input = torch.cat(
            [expanded_state, action_embedding, expanded_state * action_embedding],
            dim=-1,
        )
        policy_logits = self.policy_head(policy_input).squeeze(-1)
        outcome_logits = self.outcome_head(state_embedding).squeeze(-1)
        absolute_hp_values = self.hp_head(state_embedding).squeeze(-1)
        resource_values = self.resource_head(state_embedding).squeeze(0)
        return policy_logits, outcome_logits, absolute_hp_values, resource_values

    def forward_batch(
        self,
        state_features: Tensor,
        action_features: Tensor,
        action_batch_indices: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """Score flattened variable-action rows for a batch of decisions."""

        normalized_states = (state_features - self.state_mean) / self.state_std
        normalized_actions = (action_features - self.action_mean) / self.action_std
        state_embeddings = self.state_encoder(normalized_states)
        action_embeddings = self.action_encoder(normalized_actions)
        expanded_states = state_embeddings[action_batch_indices]
        policy_inputs = torch.cat(
            [expanded_states, action_embeddings, expanded_states * action_embeddings],
            dim=-1,
        )
        policy_logits = self.policy_head(policy_inputs).squeeze(-1)
        outcome_logits = self.outcome_head(state_embeddings).squeeze(-1)
        absolute_hp_values = self.hp_head(state_embeddings).squeeze(-1)
        resource_values = self.resource_head(state_embeddings)
        return policy_logits, outcome_logits, absolute_hp_values, resource_values


class TorchPolicyValueActionScorer:
    """Action scorer backed by the trained PyTorch policy head."""

    name = "torch_policy_value"

    def __init__(self, model: PolicyValueNetwork) -> None:
        self.model = model
        self.model.eval()

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return _model_provenance_config(self.model)

    @torch.no_grad()
    def score_actions(self, context: DecisionContext) -> list[float]:
        _validate_context_schema(self.model, context)
        state_features = torch.tensor(
            _state_features(
                context.snapshot_features,
                encode_public_context_features(context.public_run_context),
            ),
            dtype=torch.float32,
        )
        action_features = torch.tensor(
            context.legal_action_features,
            dtype=torch.float32,
        )
        logits = self.model(state_features, action_features)[0]
        return [float(value) for value in logits]

    @torch.no_grad()
    def score_action_rows(self, batch: ModelInputBatch) -> list[float]:
        _validate_batch_schema(self.model, batch)
        scores: list[float] = []
        for example_index, snapshot_features in enumerate(batch.snapshot_features):
            state_features = torch.tensor(
                _state_features(
                    snapshot_features,
                    batch.public_context_features[example_index],
                ),
                dtype=torch.float32,
            )
            action_start = batch.action_offsets[example_index]
            action_end = batch.action_offsets[example_index + 1]
            action_features = torch.tensor(
                batch.action_features[action_start:action_end],
                dtype=torch.float32,
            )
            logits = self.model(state_features, action_features)[0]
            scores.extend(float(value) for value in logits)
        return scores


class TorchPolicyValueGuidanceScorer:
    """Inference-only scorer for current policy/value checkpoints."""

    name = "torch_policy_value_guidance"

    def __init__(
        self,
        loaded: LoadedTorchPolicyValueCheckpoint,
        *,
        checkpoint_artifact_id: str,
        checkpoint_path: str | None = None,
    ) -> None:
        self.loaded = loaded
        self.model = loaded.model
        self.model.eval()
        self.checkpoint_provenance = _guidance_checkpoint_provenance(
            loaded,
            checkpoint_artifact_id=checkpoint_artifact_id,
            checkpoint_path=checkpoint_path,
        )

    @classmethod
    def from_checkpoint_path(cls, path: str | Path) -> "TorchPolicyValueGuidanceScorer":
        checkpoint_path = Path(path)
        checkpoint_bytes = checkpoint_path.read_bytes()
        loaded = load_torch_policy_value_checkpoint(str(checkpoint_path))
        checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        return cls(
            loaded,
            checkpoint_artifact_id=(
                f"{TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID}-sha256:{checkpoint_sha256}"
            ),
            checkpoint_path=str(checkpoint_path),
        )

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return self.checkpoint_provenance.to_dict()

    @torch.no_grad()
    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> SearchGuidanceInferenceResult:
        started = perf_counter()
        validate_search_guidance_context(context)
        _validate_context_schema(self.model, context)

        state_features = torch.tensor(
            _state_features(
                context.snapshot_features,
                encode_public_context_features(context.public_run_context),
            ),
            dtype=torch.float32,
        )
        action_features = torch.tensor(
            context.legal_action_features,
            dtype=torch.float32,
        )
        logits, outcome_logit, hp_value, resource_values = self.model(
            state_features,
            action_features,
        )
        probabilities = _eligible_policy_probabilities(
            logits,
            context.eligible_action_indices,
        )
        eligible_indices = set(context.eligible_action_indices)
        action_scores = [
            SearchGuidanceActionScore(
                legal_action_index=index,
                action_kind=context.legal_action_kinds[index],
                eligible=index in eligible_indices,
                policy_logit=float(logits[index]),
                policy_probability=probabilities[index],
                action_identity=_context_action_identity(context, index),
            )
            for index in range(len(context.legal_action_features))
        ]
        value_prediction = SearchGuidanceValuePrediction(
            battle_survival_probability=float(torch.sigmoid(outcome_logit).squeeze()),
            terminal_absolute_current_hp=float(hp_value.squeeze()),
            structured_resource_values={
                name: float(resource_values[index])
                for index, name in enumerate(self.model.resource_target_names)
            },
        )
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.checkpoint_provenance,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=action_scores,
            value_prediction=value_prediction,
            duration_ms=(perf_counter() - started) * 1000.0,
        )


class TorchPolicyValueEnsembleActionScorer:
    """Average standardized policy logits from compatible checkpoints."""

    name = "torch_policy_value_ensemble"

    def __init__(self, models: Sequence[PolicyValueNetwork]) -> None:
        if not models:
            raise ValueError("PyTorch policy ensemble requires at least one model")
        dimensions = {
            (
                model.state_feature_size,
                model.snapshot_feature_size,
                model.public_context_feature_size,
                model.action_feature_size,
                model.tactical_feature_schema_id,
                model.public_context_feature_schema_id,
                model.public_context_feature_schema_version,
                model.public_context_feature_names,
                model.resource_target_names,
            )
            for model in models
        }
        if len(dimensions) != 1:
            raise ValueError("PyTorch policy ensemble model dimensions do not match")
        self.models = list(models)
        for model in self.models:
            model.eval()

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "member_count": len(self.models),
            "member_model": _model_provenance_config(self.models[0]),
            "logit_standardization": "per_model_unbiased_false_std_clamp_1e-6",
        }

    @torch.no_grad()
    def score_actions(self, context: DecisionContext) -> list[float]:
        standardized_logits: list[Tensor] = []
        for model in self.models:
            _validate_context_schema(model, context)
            state_features = torch.tensor(
                _state_features(
                    context.snapshot_features,
                    encode_public_context_features(context.public_run_context),
                ),
                dtype=torch.float32,
            )
            action_features = torch.tensor(
                context.legal_action_features,
                dtype=torch.float32,
            )
            logits = model(state_features, action_features)[0]
            standardized_logits.append(
                (logits - logits.mean()) / logits.std(unbiased=False).clamp_min(1e-6)
            )
        logits = torch.stack(standardized_logits, dim=0).mean(dim=0)
        return [float(value) for value in logits]


class TorchPolicyWithKindPriorActionScorer:
    """Residual policy scorer over the deterministic action-kind prior."""

    name = "torch_policy_with_kind_prior"

    def __init__(
        self,
        model: PolicyValueNetwork,
        *,
        prior_strength: float = 0.5,
        kind_scores: Mapping[str, float] = DEFAULT_ACTION_KIND_SCORE_PRIOR,
    ) -> None:
        if prior_strength < 0.0:
            raise ValueError("action-kind prior strength cannot be negative")
        self.model = model
        self.model.eval()
        self.prior_strength = float(prior_strength)
        self.kind_scores = dict(kind_scores)

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "model": _model_provenance_config(self.model),
            "prior_strength": self.prior_strength,
            "kind_scores": dict(self.kind_scores),
        }

    @torch.no_grad()
    def score_actions(self, context: DecisionContext) -> list[float]:
        _validate_context_schema(self.model, context)
        state_features = torch.tensor(
            _state_features(
                context.snapshot_features,
                encode_public_context_features(context.public_run_context),
            ),
            dtype=torch.float32,
        )
        action_features = torch.tensor(
            context.legal_action_features,
            dtype=torch.float32,
        )
        logits = self.model(state_features, action_features)[0]
        standardized = (logits - logits.mean()) / logits.std(unbiased=False).clamp_min(
            1e-6
        )
        return [
            float(standardized[index])
            + self.prior_strength * self.kind_scores.get(kind, 0.0)
            for index, kind in enumerate(context.legal_action_kinds)
        ]


def train_torch_policy_value(
    dataset: TrainerInputDataset,
    config: TorchPolicyValueTrainingConfig | None = None,
    *,
    gate_report: TrainingGateReport | None = None,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = TRAINING_GATE_OVERRIDE_NONE,
) -> TorchPolicyValueTrainingResult:
    """Train the optional policy/value model against public trainer input."""

    active_config = config or TorchPolicyValueTrainingConfig()
    active_gate = gate_report or build_training_gate_report(
        dataset,
        gate_config,
        override=gate_override,
    )
    problems = _training_input_problems(dataset, active_config, active_gate)
    policy_target_kind = _dataset_policy_target_kind(dataset)
    torch.manual_seed(active_config.seed)
    random.seed(active_config.seed)

    snapshot_size = int(dataset.snapshot_feature_size or 1)
    action_size = int(dataset.action_feature_size or 1)
    state_size = snapshot_size + PUBLIC_CONTEXT_FEATURE_SIZE
    normalizers = (
        _feature_normalizers(dataset, snapshot_size, action_size)
        if not problems
        else (None, None, None, None)
    )
    model = PolicyValueNetwork(
        state_size,
        action_size,
        snapshot_feature_size=snapshot_size,
        public_context_feature_size=PUBLIC_CONTEXT_FEATURE_SIZE,
        public_context_feature_schema_version=PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION,
        public_context_feature_names=PUBLIC_CONTEXT_FEATURE_NAMES,
        hidden_size=active_config.hidden_size,
        state_mean=normalizers[0],
        state_std=normalizers[1],
        action_mean=normalizers[2],
        action_std=normalizers[3],
    )
    if problems:
        empty = _empty_evaluation()
        return TorchPolicyValueTrainingResult(
            model=model,
            report=TorchPolicyValueTrainingReport(
                training_ok=False,
                example_count=len(dataset.records),
                state_feature_size=state_size,
                snapshot_feature_size=snapshot_size,
                action_feature_size=action_size,
                public_context_feature_size=PUBLIC_CONTEXT_FEATURE_SIZE,
                public_context_feature_schema_version=(
                    PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION
                ),
                public_context_feature_names=PUBLIC_CONTEXT_FEATURE_NAMES,
                parameter_count=sum(
                    parameter.numel() for parameter in model.parameters()
                ),
                config=active_config,
                initial_evaluation=empty,
                final_evaluation=empty,
                gate_report=active_gate,
                policy_target_kind=policy_target_kind,
                problems=tuple(problems),
            ),
        )

    optimizer = torch.optim.Adam(model.parameters(), lr=active_config.learning_rate)
    initial = evaluate_torch_policy_value(model, dataset, active_config)
    epoch_stats: list[TorchPolicyValueEpochStats] = []
    record_indices = list(range(len(dataset.records)))
    for epoch in range(1, active_config.epochs + 1):
        random.shuffle(record_indices)
        totals = [0.0, 0.0, 0.0, 0.0, 0.0]
        model.train()
        for start in range(0, len(record_indices), active_config.batch_size):
            batch_indices = record_indices[start : start + active_config.batch_size]
            batch_records = [dataset.records[index] for index in batch_indices]
            optimizer.zero_grad()
            losses = _batch_losses(model, batch_records, active_config)
            losses[0].backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
            optimizer.step()
            for index, loss in enumerate(losses):
                totals[index] += float(loss.detach()) * len(batch_records)
        denominator = len(record_indices)
        epoch_stats.append(
            TorchPolicyValueEpochStats(
                epoch=epoch,
                average_total_loss=totals[0] / denominator,
                average_policy_loss=totals[1] / denominator,
                average_outcome_loss=totals[2] / denominator,
                average_hp_loss=totals[3] / denominator,
                average_resource_loss=totals[4] / denominator,
            )
        )
    final = evaluate_torch_policy_value(model, dataset, active_config)
    final_values = (
        final.average_total_loss,
        final.average_policy_loss,
        final.average_outcome_loss,
        final.average_hp_loss,
        final.average_resource_loss,
        final.outcome_mean_absolute_error,
        final.hp_mean_absolute_error,
        *final.resource_mean_absolute_errors.values(),
    )
    if not all(math.isfinite(value) for value in final_values):
        problems.append("non-finite final policy/value metric")
    return TorchPolicyValueTrainingResult(
        model=model,
        report=TorchPolicyValueTrainingReport(
            training_ok=not problems,
            example_count=len(dataset.records),
            state_feature_size=state_size,
            snapshot_feature_size=snapshot_size,
            action_feature_size=action_size,
            public_context_feature_size=PUBLIC_CONTEXT_FEATURE_SIZE,
            public_context_feature_schema_version=(
                PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION
            ),
            public_context_feature_names=PUBLIC_CONTEXT_FEATURE_NAMES,
            parameter_count=sum(parameter.numel() for parameter in model.parameters()),
            config=active_config,
            initial_evaluation=initial,
            final_evaluation=final,
            gate_report=active_gate,
            policy_target_kind=policy_target_kind,
            epochs=tuple(epoch_stats),
            problems=tuple(problems),
        ),
    )


@torch.no_grad()
def evaluate_torch_policy_value(
    model: PolicyValueNetwork,
    dataset: TrainerInputDataset,
    config: TorchPolicyValueTrainingConfig,
) -> TorchPolicyValueEvaluation:
    """Evaluate raw policy/value diagnostics on a trainer input dataset."""

    _validate_model_dataset_compatibility(model, dataset)
    model.eval()
    totals = [0.0, 0.0, 0.0, 0.0, 0.0]
    policy_agreement = 0
    outcome_absolute_error = 0.0
    hp_absolute_error = 0.0
    resource_absolute_errors = [0.0] * len(model.resource_target_names)
    resource_target_counts = [0] * len(model.resource_target_names)

    for record in dataset.records:
        losses = _record_losses(model, record, config)
        for index, loss in enumerate(losses):
            totals[index] += float(loss)
        state, actions = _record_tensors(record)
        logits, outcome_logit, hp_value, resource_values = model(state, actions)
        target = _record_targets(record)
        selected_global = _selected_eligible_index(
            logits, record.eligible_action_indices
        )
        policy_agreement += int(
            selected_global == _policy_target_top_index(record, target)
        )
        outcome_prediction = float(torch.sigmoid(outcome_logit).squeeze())
        outcome_absolute_error += abs(outcome_prediction - target.outcome_survived)
        hp_absolute_error += abs(float(hp_value.squeeze()) - target.terminal_current_hp)
        for index, mask in enumerate(target.resource_mask):
            if mask <= 0.0:
                continue
            resource_target_counts[index] += 1
            resource_absolute_errors[index] += abs(
                float(resource_values[index]) - target.resource_values[index]
            )

    denominator = len(dataset.records)
    resource_record_count = max(resource_target_counts, default=0)
    return TorchPolicyValueEvaluation(
        example_count=denominator,
        average_total_loss=totals[0] / denominator,
        average_policy_loss=totals[1] / denominator,
        average_outcome_loss=totals[2] / denominator,
        average_hp_loss=totals[3] / denominator,
        average_resource_loss=totals[4] / denominator,
        policy_top1_agreement=policy_agreement,
        outcome_mean_absolute_error=outcome_absolute_error / denominator,
        hp_mean_absolute_error=hp_absolute_error / denominator,
        resource_target_record_count=resource_record_count,
        resource_mean_absolute_errors={
            name: (
                resource_absolute_errors[index] / resource_target_counts[index]
                if resource_target_counts[index]
                else 0.0
            )
            for index, name in enumerate(model.resource_target_names)
        },
    )


def format_torch_policy_value_training_report(
    report: TorchPolicyValueTrainingReport,
) -> str:
    """Format T009 training, raw diagnostics, and search-eval status."""

    initial = report.initial_evaluation
    final = report.final_evaluation
    lines = [
        "PyTorch search-guidance training summary",
        "scope: public policy/value plumbing; not evidence of model strength",
        f"training ok: {_yes_no(report.training_ok)}",
        f"examples: {report.example_count}",
        f"state feature size: {report.state_feature_size}",
        f"snapshot feature size: {report.snapshot_feature_size}",
        (
            "public context feature schema: "
            f"{report.public_context_feature_schema_id} "
            f"v{report.public_context_feature_schema_version}"
        ),
        f"public context feature size: {report.public_context_feature_size}",
        f"action feature size: {report.action_feature_size}",
        f"parameters: {report.parameter_count}",
        f"epochs: {report.config.epochs}",
        f"learning rate: {report.config.learning_rate:.6g}",
        f"batch size: {report.config.batch_size}",
        (
            "targets: "
            f"policy={report.policy_target_kind}, "
            f"outcome={report.outcome_target_kind}, "
            f"hp={report.hp_target_kind}, "
            f"resources={report.structured_resource_target_kind}"
        ),
        (
            "HP target: terminal absolute current HP; "
            f"loss scale={report.config.hp_loss_scale:g}; not max-HP normalization"
        ),
        (
            "structured resources: separate masked heads over "
            + ", ".join(RESOURCE_TARGET_NAMES)
        ),
        (
            "raw policy diagnostic initial: "
            f"loss={initial.average_total_loss:.6f} "
            f"top1={initial.policy_top1_agreement}/{initial.example_count} "
            f"survival_mae={initial.outcome_mean_absolute_error:.3f} "
            f"absolute_hp_mae={initial.hp_mean_absolute_error:.3f} "
            f"resource_loss={initial.average_resource_loss:.6f}"
        ),
        (
            "raw policy diagnostic final: "
            f"loss={final.average_total_loss:.6f} "
            f"top1={final.policy_top1_agreement}/{final.example_count} "
            f"survival_mae={final.outcome_mean_absolute_error:.3f} "
            f"absolute_hp_mae={final.hp_mean_absolute_error:.3f} "
            f"resource_loss={final.average_resource_loss:.6f}"
        ),
        (
            "search-guided fixed evaluation: "
            f"{report.search_guided_fixed_evaluation_status}"
        ),
        f"search-guided fixed evaluation reason: {report.search_guided_fixed_evaluation_reason}",
        (
            "broad training allowed: "
            f"{_yes_no(report.gate_report.broad_training_allowed)}"
        ),
        f"training gate override: {report.gate_report.override}",
        "problems:",
    ]
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def format_torch_policy_value_evaluation_report(
    evaluation: TorchPolicyValueEvaluation,
    *,
    label: str = "dataset",
) -> str:
    """Format raw model diagnostics separately from search evaluation."""

    return "\n".join(
        [
            "PyTorch raw policy/value diagnostic",
            f"dataset: {label}",
            f"examples: {evaluation.example_count}",
            f"average loss: {evaluation.average_total_loss:.6f}",
            (
                "policy top-1 agreement: "
                f"{evaluation.policy_top1_agreement}/{evaluation.example_count}"
            ),
            f"survival mean absolute error: {evaluation.outcome_mean_absolute_error:.3f}",
            (
                "terminal absolute current HP mean absolute error: "
                f"{evaluation.hp_mean_absolute_error:.3f}"
            ),
            (
                "structured resource target records: "
                f"{evaluation.resource_target_record_count}/{evaluation.example_count}"
            ),
            f"structured resource vector loss: {evaluation.average_resource_loss:.6f}",
            *(
                f"structured resource {name} mean absolute error: {value:.3f}"
                for name, value in evaluation.resource_mean_absolute_errors.items()
            ),
        ]
    )


def save_torch_policy_value_checkpoint(
    result: TorchPolicyValueTrainingResult,
    path: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    training_data_provenance: Mapping[str, Any] | None = None,
) -> None:
    """Save model weights, schemas, config, and training provenance."""

    if not result.report.training_ok:
        raise ValueError("refusing to save a failed PyTorch policy/value checkpoint")
    validated_training_data_provenance = _validate_training_data_provenance(
        training_data_provenance
    )
    torch.save(
        {
            "schema_id": TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
            "format_version": TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
            "model_class": TORCH_POLICY_VALUE_MODEL_CLASS,
            "state_feature_size": result.model.state_feature_size,
            "snapshot_feature_size": result.model.snapshot_feature_size,
            "public_context_feature_size": result.model.public_context_feature_size,
            "action_feature_size": result.model.action_feature_size,
            "hidden_size": result.model.hidden_size,
            "tactical_feature_schema_id": result.model.tactical_feature_schema_id,
            "tactical_feature_schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
            "identity_vocabulary_version": IDENTITY_VOCABULARY_VERSION,
            "public_context_feature_schema_id": (
                result.model.public_context_feature_schema_id
            ),
            "public_context_feature_schema_version": (
                result.model.public_context_feature_schema_version
            ),
            "public_context_feature_names": list(
                result.model.public_context_feature_names
            ),
            "resource_target_names": list(result.model.resource_target_names),
            "resource_target_scales": list(RESOURCE_TARGET_SCALES),
            "policy_target_kind": result.report.policy_target_kind,
            "outcome_target_kind": result.report.outcome_target_kind,
            "hp_target_kind": result.report.hp_target_kind,
            "structured_resource_target_kind": (
                result.report.structured_resource_target_kind
            ),
            "model_state_dict": result.model.state_dict(),
            "training_config": result.report.config.to_dict(),
            "training_report": _json_safe_value(
                _training_report_metadata(result.report)
            ),
            "training_data_provenance": validated_training_data_provenance,
            "metadata": _json_safe_value(dict(metadata or {})),
        },
        path,
    )


def load_torch_policy_value_checkpoint(
    path: str,
) -> LoadedTorchPolicyValueCheckpoint:
    """Load a current-schema policy/value checkpoint on CPU."""

    raw = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(raw, Mapping):
        raise ValueError("PyTorch policy/value checkpoint must be a mapping")
    if raw.get("schema_id") != TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID:
        raise ValueError("unsupported PyTorch policy/value checkpoint schema")
    if raw.get("format_version") != TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION:
        raise ValueError(
            "unsupported PyTorch policy/value checkpoint format version "
            f"{raw.get('format_version')!r}"
        )
    if raw.get("model_class") != TORCH_POLICY_VALUE_MODEL_CLASS:
        raise ValueError("unsupported PyTorch policy/value model class")
    _validate_checkpoint_semantic_contract(raw)
    training_data_provenance = _validate_training_data_provenance(
        raw.get("training_data_provenance")
    )
    try:
        config = TorchPolicyValueTrainingConfig(**_mapping(raw.get("training_config")))
        state_size = _positive_int(raw.get("state_feature_size"), "state_feature_size")
        snapshot_size = _positive_int(
            raw.get("snapshot_feature_size"), "snapshot_feature_size"
        )
        public_context_size = _positive_int(
            raw.get("public_context_feature_size"),
            "public_context_feature_size",
        )
        action_size = _positive_int(
            raw.get("action_feature_size"), "action_feature_size"
        )
        hidden_size = _positive_int(raw.get("hidden_size"), "hidden_size")
        state_dict = raw["model_state_dict"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("checkpoint model dimensions or state are invalid") from exc
    if not isinstance(state_dict, Mapping):
        raise ValueError("checkpoint model_state_dict must be a mapping")
    model = PolicyValueNetwork(
        state_size,
        action_size,
        snapshot_feature_size=snapshot_size,
        public_context_feature_size=public_context_size,
        hidden_size=hidden_size,
        tactical_feature_schema_id=_required_string(
            raw.get("tactical_feature_schema_id"), "tactical_feature_schema_id"
        ),
        public_context_feature_schema_id=_required_string(
            raw.get("public_context_feature_schema_id"),
            "public_context_feature_schema_id",
        ),
        public_context_feature_schema_version=_positive_int(
            raw.get("public_context_feature_schema_version"),
            "public_context_feature_schema_version",
        ),
        public_context_feature_names=tuple(
            str(name) for name in _list(raw.get("public_context_feature_names"))
        ),
        resource_target_names=RESOURCE_TARGET_NAMES,
    )
    try:
        model.load_state_dict(state_dict, strict=True)
    except RuntimeError as exc:
        raise ValueError("checkpoint model state is incompatible") from exc
    model.eval()
    return LoadedTorchPolicyValueCheckpoint(
        model=model,
        config=config,
        metadata=_mapping(raw.get("metadata")),
        training_data_provenance=training_data_provenance,
    )


def _validate_checkpoint_semantic_contract(raw: Mapping[str, Any]) -> None:
    _require_exact(
        raw.get("tactical_feature_schema_id"),
        TACTICAL_FEATURE_SCHEMA_ID,
        "tactical_feature_schema_id",
    )
    _require_exact(
        raw.get("tactical_feature_schema_version"),
        TACTICAL_FEATURE_SCHEMA_VERSION,
        "tactical_feature_schema_version",
    )
    _require_exact(
        raw.get("identity_vocabulary_version"),
        IDENTITY_VOCABULARY_VERSION,
        "identity_vocabulary_version",
    )
    _require_exact(
        raw.get("public_context_feature_schema_id"),
        PUBLIC_CONTEXT_FEATURE_SCHEMA_ID,
        "public_context_feature_schema_id",
    )
    _require_exact(
        raw.get("public_context_feature_schema_version"),
        PUBLIC_CONTEXT_FEATURE_SCHEMA_VERSION,
        "public_context_feature_schema_version",
    )
    _require_exact(
        raw.get("public_context_feature_size"),
        PUBLIC_CONTEXT_FEATURE_SIZE,
        "public_context_feature_size",
    )
    _require_exact(
        _list(raw.get("public_context_feature_names")),
        list(PUBLIC_CONTEXT_FEATURE_NAMES),
        "public_context_feature_names",
    )
    _require_exact(
        _list(raw.get("resource_target_names")),
        list(RESOURCE_TARGET_NAMES),
        "resource_target_names",
    )
    _require_exact(
        _list(raw.get("resource_target_scales")),
        list(RESOURCE_TARGET_SCALES),
        "resource_target_scales",
    )
    policy_target_kind = _required_string(
        raw.get("policy_target_kind"), "policy_target_kind"
    )
    if policy_target_kind not in POLICY_TARGET_KINDS:
        raise ValueError(
            "checkpoint policy_target_kind "
            f"{policy_target_kind!r} is not a current supported target kind"
        )
    _require_exact(
        raw.get("outcome_target_kind"),
        OUTCOME_TARGET_KIND,
        "outcome_target_kind",
    )
    _require_exact(raw.get("hp_target_kind"), HP_TARGET_KIND, "hp_target_kind")
    _require_exact(
        raw.get("structured_resource_target_kind"),
        STRUCTURED_RESOURCE_TARGET_KIND,
        "structured_resource_target_kind",
    )


def _validate_training_data_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("training_data_provenance must be a mapping")

    raw = dict(value)
    trainer_input_sha256 = _required_string(
        raw.get("trainer_input_sha256"),
        "training_data_provenance.trainer_input_sha256",
    )
    if len(trainer_input_sha256) != 64 or any(
        char not in "0123456789abcdefABCDEF" for char in trainer_input_sha256
    ):
        raise ValueError(
            "training_data_provenance.trainer_input_sha256 must be a SHA-256 hex digest"
        )

    trainer_input_artifact_id = _required_string(
        raw.get("trainer_input_artifact_id"),
        "training_data_provenance.trainer_input_artifact_id",
    )
    expected_artifact_id = f"trainer-input-sha256:{trainer_input_sha256}"
    if trainer_input_artifact_id != expected_artifact_id:
        raise ValueError(
            "training_data_provenance.trainer_input_artifact_id must match "
            "trainer_input_sha256"
        )
    _required_string(
        raw.get("trainer_input_path"), "training_data_provenance.trainer_input_path"
    )
    _positive_int(
        raw.get("trainer_input_byte_count"),
        "training_data_provenance.trainer_input_byte_count",
    )
    _positive_int(
        raw.get("trainer_record_count"),
        "training_data_provenance.trainer_record_count",
    )
    _non_negative_int(
        raw.get("source_rollout_count"),
        "training_data_provenance.source_rollout_count",
    )
    _non_negative_int(
        raw.get("segment_count"), "training_data_provenance.segment_count"
    )
    _non_negative_int(
        raw.get("trainer_input_format_version"),
        "training_data_provenance.trainer_input_format_version",
    )
    _required_mapping(
        raw.get("generation_metadata"),
        "training_data_provenance.generation_metadata",
    )
    _required_mapping(
        raw.get("dataset_migration_report"),
        "training_data_provenance.dataset_migration_report",
    )
    _validate_controller_provenance_summary(raw.get("controller_provenance_summary"))
    _required_count_mapping(
        raw.get("information_regime_counts"),
        "training_data_provenance.information_regime_counts",
        allow_empty=False,
    )
    _required_count_mapping(
        raw.get("source_information_regime_counts"),
        "training_data_provenance.source_information_regime_counts",
        allow_empty=False,
    )
    _validate_target_source_summary(raw.get("target_source_summary"))
    _required_count_mapping(
        raw.get("distribution_counts"),
        "training_data_provenance.distribution_counts",
        allow_empty=False,
    )
    _required_count_mapping(
        raw.get("source_kind_counts"),
        "training_data_provenance.source_kind_counts",
        allow_empty=False,
    )
    _required_count_mapping(
        raw.get("sampling_component_counts"),
        "training_data_provenance.sampling_component_counts",
        allow_empty=False,
    )
    _validate_stable_source_identity_summary(raw.get("stable_source_identity_summary"))
    _required_mapping(raw.get("gate_report"), "training_data_provenance.gate_report")
    return _json_safe_value(raw)


def _validate_controller_provenance_summary(value: Any) -> None:
    summary = _required_mapping(
        value, "training_data_provenance.controller_provenance_summary"
    )
    _positive_int(
        summary.get("unique_controller_provenance_count"),
        (
            "training_data_provenance.controller_provenance_summary."
            "unique_controller_provenance_count"
        ),
    )
    provenances = summary.get("provenances")
    if not isinstance(provenances, list) or not provenances:
        raise ValueError(
            "training_data_provenance.controller_provenance_summary.provenances "
            "must be a non-empty list"
        )
    for index, provenance in enumerate(provenances):
        label = (
            "training_data_provenance.controller_provenance_summary.provenances"
            f"[{index}]"
        )
        row = _required_mapping(provenance, label)
        digest = _required_string(row.get("digest"), f"{label}.digest")
        if not digest.startswith("sha256:"):
            raise ValueError(f"{label}.digest must use sha256: prefix")
        _positive_int(row.get("count"), f"{label}.count")
        _required_mapping(row.get("provenance"), f"{label}.provenance")


def _validate_target_source_summary(value: Any) -> None:
    summary = _required_mapping(value, "training_data_provenance.target_source_summary")
    expected = {
        "outcome_target_kind": OUTCOME_TARGET_KIND,
        "hp_target_kind": HP_TARGET_KIND,
        "structured_resource_target_kind": STRUCTURED_RESOURCE_TARGET_KIND,
        "structured_resource_target_names": list(RESOURCE_TARGET_NAMES),
    }
    for key, expected_value in expected.items():
        _require_exact(
            summary.get(key),
            expected_value,
            f"training_data_provenance.target_source_summary.{key}",
        )
    policy_target_kind = _required_string(
        summary.get("policy_target_kind"),
        "training_data_provenance.target_source_summary.policy_target_kind",
    )
    if policy_target_kind not in POLICY_TARGET_KINDS:
        raise ValueError(
            "training_data_provenance.target_source_summary.policy_target_kind "
            f"{policy_target_kind!r} is not supported"
        )
    for key in (
        "policy_target_source",
        "outcome_target_source",
        "hp_target_source",
        "structured_resource_target_source",
    ):
        _required_string(
            summary.get(key), f"training_data_provenance.target_source_summary.{key}"
        )


def _validate_stable_source_identity_summary(value: Any) -> None:
    summary = _required_mapping(
        value, "training_data_provenance.stable_source_identity_summary"
    )
    _non_negative_int(
        summary.get("unique_source_count"),
        "training_data_provenance.stable_source_identity_summary.unique_source_count",
    )
    _non_negative_int(
        summary.get("missing_source_identity_count"),
        (
            "training_data_provenance.stable_source_identity_summary."
            "missing_source_identity_count"
        ),
    )
    _required_count_mapping(
        summary.get("identity_kind_counts"),
        (
            "training_data_provenance.stable_source_identity_summary."
            "identity_kind_counts"
        ),
        allow_empty=True,
    )


def _require_exact(value: Any, expected: Any, label: str) -> None:
    if value != expected:
        raise ValueError(
            f"checkpoint {label} {value!r} does not match current {expected!r}"
        )


def _required_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(value)


def _required_count_mapping(
    value: Any,
    label: str,
    *,
    allow_empty: bool,
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{label}.{key} must be a non-negative integer")
        result[str(key)] = count
    if not result and not allow_empty:
        raise ValueError(f"{label} must not be empty")
    return result


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class _RecordTargets:
    policy_target: list[float]
    outcome_survived: float
    terminal_current_hp: float
    resource_values: list[float]
    resource_mask: list[float]


def _record_losses(
    model: PolicyValueNetwork,
    record: TrainerInputRecord,
    config: TorchPolicyValueTrainingConfig,
) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
    state_features, action_features = _record_tensors(record)
    logits, outcome_logit, hp_value, resource_values = model(
        state_features,
        action_features,
    )
    target = _record_targets(record)
    eligible = torch.tensor(record.eligible_action_indices, dtype=torch.long)
    policy_target = torch.tensor(target.policy_target, dtype=torch.float32)[eligible]
    policy_target = policy_target / policy_target.sum().clamp_min(1e-6)
    policy_loss = -(policy_target * F.log_softmax(logits[eligible], dim=0)).sum()
    outcome_loss = F.binary_cross_entropy_with_logits(
        outcome_logit.squeeze(),
        torch.tensor(target.outcome_survived, dtype=torch.float32),
    )
    hp_loss = F.mse_loss(
        hp_value.squeeze() / config.hp_loss_scale,
        torch.tensor(target.terminal_current_hp / config.hp_loss_scale),
    )
    resource_loss = _resource_loss(
        resource_values.unsqueeze(0) if resource_values.ndim == 1 else resource_values,
        [target],
    )
    total_loss = (
        config.policy_loss_weight * policy_loss
        + config.outcome_loss_weight * outcome_loss
        + config.hp_loss_weight * hp_loss
        + config.resource_loss_weight * resource_loss
    )
    return total_loss, policy_loss, outcome_loss, hp_loss, resource_loss


def _batch_losses(
    model: PolicyValueNetwork,
    records: list[TrainerInputRecord],
    config: TorchPolicyValueTrainingConfig,
) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
    states = torch.tensor(
        [
            _state_features(
                record.snapshot_features,
                _record_public_context_features(record),
            )
            for record in records
        ],
        dtype=torch.float32,
    )
    action_counts = [len(record.legal_action_features) for record in records]
    actions = torch.tensor(
        [features for record in records for features in record.legal_action_features],
        dtype=torch.float32,
    )
    action_batch_indices = torch.repeat_interleave(
        torch.arange(len(records), dtype=torch.long),
        torch.tensor(action_counts, dtype=torch.long),
    )
    logits, outcome_logits, hp_values, resource_values = model.forward_batch(
        states,
        actions,
        action_batch_indices,
    )
    targets = [_record_targets(record) for record in records]
    policy_losses: list[Tensor] = []
    offset = 0
    for record, target, action_count in zip(
        records, targets, action_counts, strict=True
    ):
        eligible = torch.tensor(
            [offset + index for index in record.eligible_action_indices],
            dtype=torch.long,
        )
        policy_target = torch.tensor(target.policy_target, dtype=torch.float32)[
            record.eligible_action_indices
        ]
        policy_target = policy_target / policy_target.sum().clamp_min(1e-6)
        policy_losses.append(
            -(policy_target * F.log_softmax(logits[eligible], dim=0)).sum()
        )
        offset += action_count
    policy_loss = torch.stack(policy_losses).mean()
    outcome_loss = F.binary_cross_entropy_with_logits(
        outcome_logits,
        torch.tensor(
            [target.outcome_survived for target in targets], dtype=torch.float32
        ),
    )
    hp_loss = F.mse_loss(
        hp_values / config.hp_loss_scale,
        torch.tensor(
            [target.terminal_current_hp / config.hp_loss_scale for target in targets],
            dtype=torch.float32,
        ),
    )
    resource_loss = _resource_loss(resource_values, targets)
    total_loss = (
        config.policy_loss_weight * policy_loss
        + config.outcome_loss_weight * outcome_loss
        + config.hp_loss_weight * hp_loss
        + config.resource_loss_weight * resource_loss
    )
    return total_loss, policy_loss, outcome_loss, hp_loss, resource_loss


def _resource_loss(
    resource_values: Tensor,
    targets: Sequence[_RecordTargets],
) -> Tensor:
    values = torch.tensor(
        [target.resource_values for target in targets],
        dtype=torch.float32,
    )
    masks = torch.tensor(
        [target.resource_mask for target in targets],
        dtype=torch.float32,
    )
    if masks.sum() <= 0:
        return resource_values.sum() * 0.0
    scales = torch.tensor(RESOURCE_TARGET_SCALES, dtype=torch.float32)
    squared = ((resource_values - values) / scales).pow(2) * masks
    return squared.sum() / masks.sum().clamp_min(1.0)


def _record_tensors(record: TrainerInputRecord) -> tuple[Tensor, Tensor]:
    return (
        torch.tensor(
            _state_features(
                record.snapshot_features,
                _record_public_context_features(record),
            ),
            dtype=torch.float32,
        ),
        torch.tensor(record.legal_action_features, dtype=torch.float32),
    )


def _record_targets(record: TrainerInputRecord) -> _RecordTargets:
    outcome = _available_outcome(record)
    policy_target = list(record.policy_target)
    if len(policy_target) != len(record.legal_action_features):
        raise ValueError(
            f"record {record.example_index}: policy target length "
            f"{len(policy_target)} does not match legal action count "
            f"{len(record.legal_action_features)}"
        )
    eligible_target_sum = sum(
        policy_target[index]
        for index in record.eligible_action_indices
        if 0 <= index < len(policy_target)
    )
    if eligible_target_sum <= 0.0:
        raise ValueError(
            f"record {record.example_index}: policy target has no eligible weight"
        )
    survived_field = _field(outcome.get("battle_survived"))
    hp_field = _field(outcome.get("terminal_absolute_current_hp"))
    if survived_field.get("status") != "available":
        raise ValueError(
            f"record {record.example_index}: missing battle survival target"
        )
    if hp_field.get("status") != "available":
        raise ValueError(
            f"record {record.example_index}: missing terminal absolute current HP target"
        )
    resource_values, resource_mask = _resource_targets(outcome)
    return _RecordTargets(
        policy_target=policy_target,
        outcome_survived=1.0 if bool(survived_field.get("value")) else 0.0,
        terminal_current_hp=float(hp_field.get("value")),
        resource_values=resource_values,
        resource_mask=resource_mask,
    )


def _dataset_policy_target_kind(dataset: TrainerInputDataset) -> str:
    kinds = sorted({record.policy_target_kind for record in dataset.records})
    if len(kinds) == 1:
        return kinds[0]
    if not kinds:
        return POLICY_TARGET_KIND_BEHAVIOR
    return "mixed"


def _policy_target_top_index(
    record: TrainerInputRecord,
    target: _RecordTargets,
) -> int:
    eligible = [
        index
        for index in record.eligible_action_indices
        if 0 <= index < len(target.policy_target)
    ]
    if not eligible:
        return -1
    return max(eligible, key=lambda index: target.policy_target[index])


def _resource_targets(outcome: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    values = [0.0 for _ in RESOURCE_TARGET_NAMES]
    mask = [0.0 for _ in RESOURCE_TARGET_NAMES]
    terminal = _mapping(outcome.get("terminal"))

    def assign(index: int, value: Any) -> None:
        if isinstance(value, bool):
            values[index] = 1.0 if value else 0.0
            mask[index] = 1.0
        elif isinstance(value, (int, float)):
            values[index] = float(value)
            mask[index] = 1.0

    max_hp = _field(outcome.get("terminal_max_hp"))
    if max_hp.get("status") == "available":
        assign(0, max_hp.get("value"))
    gold = _field(terminal.get("gold"))
    if gold.get("status") == "available":
        assign(1, gold.get("value"))
    potions = _field(terminal.get("potion_slots"))
    if potions.get("status") == "available" and isinstance(potions.get("value"), list):
        assign(
            2,
            sum(
                1
                for item in potions["value"]
                if isinstance(item, Mapping) and not bool(item.get("is_empty"))
            ),
        )
    deck = _field(terminal.get("deck"))
    if deck.get("status") == "available" and isinstance(deck.get("value"), list):
        assign(3, len(deck["value"]))
    curses = _field(terminal.get("curses"))
    if curses.get("status") == "available" and isinstance(curses.get("value"), list):
        assign(4, len(curses["value"]))
    relics = _field(terminal.get("relics"))
    if relics.get("status") == "available" and isinstance(relics.get("value"), list):
        assign(5, len(relics["value"]))
    keys = _field(terminal.get("keys"))
    if keys.get("status") == "available" and isinstance(keys.get("value"), Mapping):
        key_values = keys["value"]
        assign(6, key_values.get("blue_key"))
        assign(7, key_values.get("green_key"))
        assign(8, key_values.get("red_key"))
    return values, mask


def encode_public_context_features(public_context: Mapping[str, Any]) -> list[float]:
    """Compatibility wrapper for the shared public-context encoder."""

    return shared_public_context_features(
        public_context,
        PUBLIC_CONTEXT_AVAILABLE,
    )


def _record_public_context_features(record: TrainerInputRecord) -> list[float]:
    return shared_public_context_features(
        record.public_run_context,
        record.public_context_status,
    )


def _state_features(
    snapshot_features: Sequence[float],
    public_context_features: Sequence[float],
) -> list[float]:
    return [
        *(float(value) for value in snapshot_features),
        *(float(value) for value in public_context_features),
    ]


def _feature_normalizers(
    dataset: TrainerInputDataset,
    snapshot_size: int,
    action_size: int,
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    states = torch.tensor(
        [
            _state_features(
                record.snapshot_features,
                _record_public_context_features(record),
            )
            for record in dataset.records
        ],
        dtype=torch.float32,
    )
    actions = torch.tensor(
        [
            features
            for record in dataset.records
            for features in record.legal_action_features
        ],
        dtype=torch.float32,
    )
    if states.shape[1] != snapshot_size + PUBLIC_CONTEXT_FEATURE_SIZE:
        raise ValueError("state feature normalizer shape mismatch")
    if actions.shape[1] != action_size:
        raise ValueError("action feature normalizer shape mismatch")
    return (
        states.mean(dim=0),
        states.std(dim=0, unbiased=False).clamp_min(1.0),
        actions.mean(dim=0),
        actions.std(dim=0, unbiased=False).clamp_min(1.0),
    )


def _training_input_problems(
    dataset: TrainerInputDataset,
    config: TorchPolicyValueTrainingConfig,
    gate_report: TrainingGateReport,
) -> list[str]:
    problems = list(dataset.problems)
    if not gate_report.training_allowed:
        problems.append("broad training gate failed and no named override was supplied")
    if dataset.format_version != TRAINER_INPUT_DATASET_FORMAT_VERSION:
        problems.append(
            f"unsupported trainer input format version {dataset.format_version}"
        )
    if dataset.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        problems.append(
            f"unsupported tactical feature schema {dataset.tactical_feature_schema_id!r}"
        )
    if not dataset.records:
        problems.append("trainer input dataset has no records")
    if not dataset.snapshot_feature_size:
        problems.append("trainer input dataset is missing snapshot feature size")
    if not dataset.action_feature_size:
        problems.append("trainer input dataset is missing action feature size")
    if dataset.records:
        encoded_context = encode_public_context_model_input(
            public_context_status=dataset.records[0].public_context_status,
            public_run_context=dataset.records[0].public_run_context,
        )
        context_size = len(encoded_context.public_context_features)
        if context_size != PUBLIC_CONTEXT_FEATURE_SIZE:
            problems.append(
                "trainer input public context feature size "
                f"{context_size} does not match {PUBLIC_CONTEXT_FEATURE_SIZE}"
            )
    target_kinds = {record.policy_target_kind for record in dataset.records}
    if len(target_kinds) > 1:
        problems.append(
            "trainer input dataset mixes policy target kinds: "
            + ", ".join(sorted(target_kinds))
        )
    for record in dataset.records:
        problems.extend(_record_training_problems(record))
    if config.epochs <= 0:
        problems.append("training epochs must be positive")
    if config.learning_rate <= 0.0:
        problems.append("training learning rate must be positive")
    if config.hidden_size <= 0:
        problems.append("training hidden size must be positive")
    if config.hp_loss_scale <= 0.0:
        problems.append("HP loss scale must be positive")
    if config.batch_size <= 0:
        problems.append("training batch size must be positive")
    if (
        min(
            config.policy_loss_weight,
            config.outcome_loss_weight,
            config.hp_loss_weight,
            config.resource_loss_weight,
        )
        < 0.0
    ):
        problems.append("training loss weights cannot be negative")
    if (
        config.policy_loss_weight
        + config.outcome_loss_weight
        + config.hp_loss_weight
        + config.resource_loss_weight
        <= 0.0
    ):
        problems.append("at least one training loss weight must be positive")
    return list(dict.fromkeys(problems))


def _record_training_problems(record: TrainerInputRecord) -> list[str]:
    problems: list[str] = []
    encoded_context = encode_public_context_model_input(
        public_context_status=record.public_context_status,
        public_run_context=record.public_run_context,
    )
    problems.extend(
        f"record {record.example_index}: public context model input: {problem}"
        for problem in encoded_context.problems
    )
    if record.structured_battle_outcome_status != BATTLE_RESOURCE_OUTCOME_AVAILABLE:
        problems.append(
            f"record {record.example_index}: structured battle outcome is "
            f"{record.structured_battle_outcome_status}"
        )
        return problems
    try:
        _record_targets(record)
    except (IndexError, ValueError) as exc:
        problems.append(str(exc))
    return problems


def _validate_model_dataset_compatibility(
    model: PolicyValueNetwork,
    dataset: TrainerInputDataset,
) -> None:
    problems: list[str] = []
    if not dataset.records:
        problems.append("trainer input dataset has no records")
    if dataset.tactical_feature_schema_id != model.tactical_feature_schema_id:
        problems.append(
            "trainer input tactical feature schema "
            f"{dataset.tactical_feature_schema_id!r} does not match model "
            f"{model.tactical_feature_schema_id!r}"
        )
    if dataset.snapshot_feature_size != model.snapshot_feature_size:
        problems.append("trainer input snapshot feature size does not match model")
    if dataset.action_feature_size != model.action_feature_size:
        problems.append("trainer input action feature size does not match model")
    for record in dataset.records:
        problems.extend(_record_training_problems(record))
    if problems:
        raise ValueError("; ".join(dict.fromkeys(problems)))


def _validate_context_schema(
    model: PolicyValueNetwork,
    context: DecisionContext,
) -> None:
    if context.tactical_feature_schema_id != model.tactical_feature_schema_id:
        raise ValueError(
            "decision context tactical feature schema "
            f"{context.tactical_feature_schema_id!r} does not match model "
            f"{model.tactical_feature_schema_id!r}"
        )
    if len(context.snapshot_features) != model.snapshot_feature_size:
        raise ValueError(
            f"snapshot feature size {len(context.snapshot_features)} does not match "
            f"model {model.snapshot_feature_size}"
        )
    bad_action_size = next(
        (
            len(features)
            for features in context.legal_action_features
            if len(features) != model.action_feature_size
        ),
        None,
    )
    if bad_action_size is not None:
        raise ValueError(
            f"action feature size {bad_action_size} does not match "
            f"model {model.action_feature_size}"
        )
    context_features = encode_public_context_features(context.public_run_context)
    if len(context_features) != model.public_context_feature_size:
        raise ValueError(
            "public context feature size "
            f"{len(context_features)} does not match model "
            f"{model.public_context_feature_size}"
        )


def _validate_batch_schema(model: PolicyValueNetwork, batch: ModelInputBatch) -> None:
    if batch.tactical_feature_schema_id != model.tactical_feature_schema_id:
        raise ValueError("model input tactical feature schema does not match model")
    if batch.snapshot_feature_size != model.snapshot_feature_size:
        raise ValueError("model input snapshot feature size does not match model")
    if batch.action_feature_size != model.action_feature_size:
        raise ValueError("model input action feature size does not match model")
    if batch.public_context_feature_schema_id != model.public_context_feature_schema_id:
        raise ValueError(
            "model input public context feature schema does not match model"
        )
    if (
        batch.public_context_feature_schema_version
        != model.public_context_feature_schema_version
    ):
        raise ValueError(
            "model input public context feature schema version does not match model"
        )
    if batch.public_context_feature_size != model.public_context_feature_size:
        raise ValueError("model input public context feature size does not match model")
    if tuple(batch.public_context_feature_names) != model.public_context_feature_names:
        raise ValueError("model input public context feature names do not match model")


def _guidance_checkpoint_provenance(
    loaded: LoadedTorchPolicyValueCheckpoint,
    *,
    checkpoint_artifact_id: str,
    checkpoint_path: str | None,
) -> SearchGuidanceCheckpointProvenance:
    training_provenance = dict(loaded.training_data_provenance)
    target_summary = _mapping(training_provenance.get("target_source_summary"))
    policy_target_kind = _required_string(
        target_summary.get("policy_target_kind"),
        "training_data_provenance.target_source_summary.policy_target_kind",
    )
    policy_target_source = _required_string(
        target_summary.get("policy_target_source"),
        "training_data_provenance.target_source_summary.policy_target_source",
    )
    information_regime_counts = _required_count_mapping(
        training_provenance.get("information_regime_counts"),
        "training_data_provenance.information_regime_counts",
        allow_empty=False,
    )
    source_information_regime_counts = _required_count_mapping(
        training_provenance.get("source_information_regime_counts"),
        "training_data_provenance.source_information_regime_counts",
        allow_empty=False,
    )
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id=TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
        checkpoint_format_version=TORCH_POLICY_VALUE_CHECKPOINT_FORMAT_VERSION,
        checkpoint_artifact_id=checkpoint_artifact_id,
        checkpoint_path=checkpoint_path,
        model_class=TORCH_POLICY_VALUE_MODEL_CLASS,
        model_config=_model_provenance_config(loaded.model),
        trainer_input_artifact_id=_required_string(
            training_provenance.get("trainer_input_artifact_id"),
            "training_data_provenance.trainer_input_artifact_id",
        ),
        trainer_input_sha256=_required_string(
            training_provenance.get("trainer_input_sha256"),
            "training_data_provenance.trainer_input_sha256",
        ),
        policy_target_kind=policy_target_kind,
        policy_target_source=policy_target_source,
        policy_target_kind_counts=_optional_count_mapping(
            target_summary.get("policy_target_kind_counts"),
        ),
        policy_target_source_counts=_optional_count_mapping(
            target_summary.get("policy_target_source_counts"),
        ),
        information_regime_counts=information_regime_counts,
        source_information_regime_counts=source_information_regime_counts,
        oracle_like_supervision=_oracle_like_supervision(
            policy_target_kind,
            policy_target_source,
            information_regime_counts,
            source_information_regime_counts,
        ),
        training_data_provenance=training_provenance,
    )


def _eligible_policy_probabilities(
    logits: Tensor,
    eligible_indices: Sequence[int],
) -> list[float]:
    eligible = torch.tensor(list(eligible_indices), dtype=torch.long)
    eligible_probabilities = torch.softmax(logits[eligible], dim=0)
    probabilities = [0.0 for _ in range(int(logits.shape[0]))]
    for local_index, action_index in enumerate(eligible_indices):
        probabilities[action_index] = float(eligible_probabilities[local_index])
    return probabilities


def _context_action_identity(
    context: DecisionContext,
    index: int,
) -> dict[str, Any]:
    if index < 0 or index >= len(context.tactical_legal_actions):
        return {}
    action = context.tactical_legal_actions[index]
    if not isinstance(action, Mapping):
        return {}
    return _mapping(action.get("identity"))


def _optional_count_mapping(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    return _required_count_mapping(
        value, "policy target count mapping", allow_empty=True
    )


def _oracle_like_supervision(
    policy_target_kind: str,
    policy_target_source: str,
    information_regime_counts: Mapping[str, int],
    source_information_regime_counts: Mapping[str, int],
) -> bool:
    evidence = {
        str(value).lower()
        for value in {
            policy_target_kind,
            policy_target_source,
            *information_regime_counts.keys(),
            *source_information_regime_counts.keys(),
        }
    }
    return any(
        "oracle" in value or value == "full_simulator_state_oracle_like"
        for value in evidence
    )


def _selected_eligible_index(logits: Tensor, eligible_indices: Sequence[int]) -> int:
    eligible = torch.tensor(list(eligible_indices), dtype=torch.long)
    selected_local = int(torch.argmax(logits[eligible]))
    return int(eligible_indices[selected_local])


def _available_outcome(record: TrainerInputRecord) -> Mapping[str, Any]:
    if record.structured_battle_outcome_status != BATTLE_RESOURCE_OUTCOME_AVAILABLE:
        raise ValueError(
            f"record {record.example_index}: structured battle outcome is unavailable"
        )
    return record.structured_battle_outcome


def _field(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items_if_available(field: Mapping[str, Any]) -> list[Any]:
    if field.get("availability") != "available":
        return []
    value = field.get("items", field.get("value"))
    return list(value) if isinstance(value, list) else []


def _available_number(field: Any) -> float:
    wrapped = _field(field)
    if wrapped.get("availability") != "available":
        return 0.0
    value = wrapped.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _normalizer_value(value: Tensor | None, size: int, *, fill: float) -> Tensor:
    if value is None:
        return torch.full((size,), fill, dtype=torch.float32)
    normalized = value.detach().clone().to(dtype=torch.float32)
    if normalized.shape != (size,):
        raise ValueError(
            f"normalizer shape {tuple(normalized.shape)} does not match {(size,)}"
        )
    return normalized


def _empty_evaluation() -> TorchPolicyValueEvaluation:
    return TorchPolicyValueEvaluation(
        example_count=0,
        average_total_loss=0.0,
        average_policy_loss=0.0,
        average_outcome_loss=0.0,
        average_hp_loss=0.0,
        average_resource_loss=0.0,
        policy_top1_agreement=0,
        outcome_mean_absolute_error=0.0,
        hp_mean_absolute_error=0.0,
        resource_target_record_count=0,
        resource_mean_absolute_errors={name: 0.0 for name in RESOURCE_TARGET_NAMES},
    )


def _model_provenance_config(model: PolicyValueNetwork) -> dict[str, Any]:
    return {
        "checkpoint_schema_id": TORCH_POLICY_VALUE_CHECKPOINT_SCHEMA_ID,
        "model_class": TORCH_POLICY_VALUE_MODEL_CLASS,
        "information_regime": "normal_public_policy",
        "state_feature_size": model.state_feature_size,
        "snapshot_feature_size": model.snapshot_feature_size,
        "public_context_feature_schema_id": model.public_context_feature_schema_id,
        "public_context_feature_schema_version": (
            model.public_context_feature_schema_version
        ),
        "public_context_feature_size": model.public_context_feature_size,
        "public_context_feature_names": list(model.public_context_feature_names),
        "action_feature_size": model.action_feature_size,
        "tactical_feature_schema_id": model.tactical_feature_schema_id,
        "resource_target_names": list(model.resource_target_names),
    }


def _training_report_metadata(
    report: TorchPolicyValueTrainingReport,
) -> dict[str, Any]:
    return {
        "training_ok": report.training_ok,
        "example_count": report.example_count,
        "state_feature_size": report.state_feature_size,
        "snapshot_feature_size": report.snapshot_feature_size,
        "action_feature_size": report.action_feature_size,
        "public_context_feature_size": report.public_context_feature_size,
        "public_context_feature_schema_id": report.public_context_feature_schema_id,
        "public_context_feature_schema_version": (
            report.public_context_feature_schema_version
        ),
        "public_context_feature_names": list(report.public_context_feature_names),
        "parameter_count": report.parameter_count,
        "policy_target_kind": report.policy_target_kind,
        "outcome_target_kind": report.outcome_target_kind,
        "hp_target_kind": report.hp_target_kind,
        "structured_resource_target_kind": report.structured_resource_target_kind,
        "gate_report": report.gate_report.to_dict(),
        "initial_evaluation": asdict(report.initial_evaluation),
        "final_evaluation": asdict(report.final_evaluation),
        "search_guided_fixed_evaluation_status": (
            report.search_guided_fixed_evaluation_status
        ),
        "search_guided_fixed_evaluation_reason": (
            report.search_guided_fixed_evaluation_reason
        ),
        "problems": list(report.problems),
    }


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
