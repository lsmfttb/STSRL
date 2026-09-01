# T080: Battle Value-Target Semantic Alignment Audit

## Objective

Determine whether the battle-survival value head used inside Search v2 is trained on a target with the same continuation-policy semantics that Search v2 expects at hypothetical leaf states.

This task addresses the post-T079 Priority-2 decision boundary recorded in research ledger #85. T079 completed with an `AMBIGUOUS` exact-transposition result because current native state identity is too opaque for a cheap exact-state-utilization conclusion. T080 therefore does not continue T079 instrumentation. It tests the strongest current model-side hypothesis suggested by T070:

```text
prior_only > prior_value >> value_only
```

The task is a provenance and semantic-alignment diagnostic. It does not train a replacement checkpoint, change features, change model architecture, change Search v2, alter the simulator, or publish a controller.

## Current Semantic Evidence To Verify

Current `main` contains an explicit candidate mismatch that T080 must audit rather than assume away:

1. `torch_policy_value.py` names the outcome target `terminal_battle_survival_probability` and trains it from `TrainerInputRecord.structured_battle_outcome.battle_survived`.
2. T043's Oracle-teacher bridge constructs policy targets from the Oracle teacher row (`oracle_teacher_row.teacher_action` or `oracle_teacher_row.soft_visit_target`) while constructing survival/outcome targets from the source battle record via `_battle_survived(source)` and `source.completed_battle_resource_outcome`.
3. Search v2 requests `battle_survival_probability` from the checkpoint at the learned-leaf boundary `after_first_action_from_newly_expanded_node` and passes that scalar directly to the native leaf-value callback.

This establishes a concrete semantic-risk surface: the policy target can describe an Oracle-improved action distribution while the value target can describe the realized source/behavior continuation outcome. T080 must determine the exact scope of that relationship in the retained checkpoint training data and classify it without assuming that a behavior-policy Monte Carlo outcome is automatically a valid Search-v2 leaf value.

## Dependencies

- T079 is complete and its exact-transposition hypothesis is parked, not closed.
- T070 provides the observed ablation signal motivating the value audit.
- T043 provides the retained policy/value checkpoint and its trainer-input provenance.
- T062 defines the Search v2 learned-leaf value consumption boundary.
- T024/T026 define the Oracle-teacher bridge and checkpoint inference contracts.
- T033 remains the public-context input boundary.

T034 is not a dependency. T080 does not attempt to resolve Oracle-to-public hidden-information ambiguity; it holds that separate research problem fixed.

## Frozen Anchors

The primary checkpoint is the exact T043 checkpoint consumed by T062/T070:

```text
sha256 = a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4
```

T080 must load its stored `training_data_provenance`, recover or verify the exact trainer-input artifact identity recorded there, and fail closed if the checkpoint/trainer-input lineage cannot be reproduced exactly. Do not substitute a newly trained checkpoint or a nearby T043 artifact.

The T070 primary cohort remains contextual evidence only:

```text
sha256 = b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608
```

No T070 battle rerun is required for the primary T080 classification.

## Scientific Questions

T080 must answer, in order:

1. **What exact quantity trains the value head?** Trace the checkpoint outcome head from loss construction back through trainer records to the source artifact field that supplies each label.
2. **What exact quantity does Search v2 consume?** Trace the value callback from the checkpoint prediction to the native learned-leaf boundary and document its intended continuation semantics.
3. **Do policy and value labels in the frozen T043 trainer data arise from the same continuation policy?** For every auditable row, distinguish Oracle-teacher policy target provenance from behavior/source action provenance and source battle-outcome provenance.
4. **How often is the distinction operational rather than merely nominal?** Quantify rows where the Oracle teacher's top target action differs from the recorded behavior action while the value target remains the source battle outcome.
5. **Can current artifacts prove semantic alignment despite different field provenance?** Alignment requires evidence that the source continuation policy/outcome is the same policy/value object Search v2 intends to approximate, not merely matching field names or a binary win/loss range.

## Required Audit Outputs

Produce one versioned, machine-readable audit over the exact frozen T043 trainer input with at least:

- checkpoint SHA-256 and checkpoint semantic metadata;
- trainer-input SHA-256, row count, schema/version, generation metadata, and source identities;
- `policy_target_kind` and `policy_target_source` counts;
- behavior-action availability counts;
- source/outcome target lineage for `battle_survived`;
- per-row stable action comparison when behavior action is available:
  - teacher target top action identity;
  - behavior action identity;
  - same/different;
- overall and stratified teacher-vs-behavior divergence rates by available source metadata such as assistance level, act, room type, source kind, and distribution kind;
- value-label counts for survived/lost and any unavailable outcome rows;
- a static call-chain report showing the exact Search v2 learned-leaf consumer and the exact T043 training producer;
- explicit unresolved fields where artifacts cannot establish continuation-policy semantics.

Do not infer semantic alignment from equal action indices without stable action identity. Do not infer alignment from the names `battle_survived` and `battle_survival_probability` alone.

## Optional Counterfactual Check

A small counterfactual continuation check is allowed only if the static/provenance audit cannot classify the semantic contract and only if it can be implemented with existing accepted restore/search/controller surfaces.

If used, it must:

- select rows outcome-blind from the exact frozen trainer artifact;
- preserve the same restored hidden simulator state for compared continuations;
- clearly name the continuation controller being estimated;
- keep source/behavior continuation, Oracle/search continuation, and public-information interpretation separate;
- not modify Search v2 or `sts_lightspeed`;
- not become a broad new teacher-data collection task.

T080 should prefer the static/provenance classification when it is sufficient.

## Precommitted Classification

T080 ends in exactly one of the following classifications.

### `VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED`

Require all of:

1. the frozen checkpoint and trainer-input lineage are exact and auditable;
2. the value head is trained from realized source/behavior battle outcomes;
3. Search v2 consumes that head as a learned value at hypothetical tree leaves;
4. the trainer data provide Oracle-improved policy targets that are not, as a contract, the same continuation policy that generated the source outcome;
5. no retained provenance establishes that the source outcome is an unbiased/defined target for the Search v2 continuation policy;
6. at least one auditable row has a teacher-target action different from the recorded behavior action while retaining the same source-outcome value target.

Interpretation: the current training contract mixes an improved policy target with a value target from a different continuation-policy source. This does not prove value functions are unsuitable; it justifies a separate bounded value-target repair experiment.

### `VALUE_TARGET_SEMANTICS_ALIGNED`

Require all of:

1. exact frozen provenance is available;
2. the value label can be proven to estimate the same continuation-policy value Search v2 requests at its learned-leaf boundary;
3. Oracle policy-target generation and value-target generation are contractually compatible rather than merely correlated;
4. no material row-level provenance contradiction is present.

Interpretation: value-target semantics move down the priority list; feature/encoding quality becomes the next primary model-side hypothesis.

### `VALUE_TARGET_SEMANTICS_UNRESOLVED`

Use when exact lineage is valid but the available artifacts cannot establish either semantic relationship without a new counterfactual dataset or other material experiment.

Interpretation: publish no repair and no feature-encoding task automatically. Planner must decide whether the minimum counterfactual continuation evidence is cheaper/more informative than moving to the feature audit.

## Decision Rule After Classification

- `VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED` -> Planner may publish one separate, bounded value-target repair experiment. The repair must change target semantics only as far as possible and keep feature/model/search changes frozen.
- `VALUE_TARGET_SEMANTICS_ALIGNED` -> do not create value-target variants; move to feature/encoding semantics audit.
- `VALUE_TARGET_SEMANTICS_UNRESOLVED` -> no automatic successor; compare the cost of a minimal continuation-value experiment against the feature audit.

In every case, update research ledger #85 with the accepted conclusion and provenance before publishing the next scientific task.

## Out Of Scope

- retraining or fine-tuning a checkpoint;
- changing policy targets;
- changing tactical/public-context features;
- replacing hash-as-float categorical identity;
- selecting Transformer/GNN/set/sequence architectures;
- changing Search v2 priors, leaf boundary, backup, rollout, root selection, or budget;
- transposition/state-identity repair or further T079 instrumentation;
- new `sts_lightspeed` semantics;
- T034 hidden-future sampling;
- T063/T066 promotion;
- complete-run reachability or later-act scale-up;
- human trajectories, labels, rankings, or handcrafted strategy supervision.

## Acceptance Criteria

1. Exact T043 checkpoint SHA and trainer-input provenance are verified before classification.
2. The complete producer chain for `battle_survived` and the complete Search v2 consumer chain for `battle_survival_probability` are recorded with file/function-level provenance.
3. Oracle teacher policy target, behavior action, and source battle outcome remain separate fields in all analysis.
4. All auditable frozen trainer rows are counted exactly once; unavailable behavior/outcome data are reported rather than imputed.
5. Teacher-vs-behavior divergence uses stable action identity and is reported overall and by available source strata.
6. The terminal classification applies the precommitted semantic rules without post-hoc threshold tuning.
7. No model training, feature change, simulator change, Search v2 change, transposition work, or controller promotion occurs.
8. Research ledger #85 is updated after accepted evidence and before any successor scientific task is published.

## Verification

Run standard repository gates plus focused tests for the audit parser, checkpoint/trainer provenance validation, stable action-identity comparison, classification logic, deterministic report generation, and `git diff --check`.

The primary T080 path is offline and should not require a native simulator build. If the optional counterfactual check becomes necessary, it must first pass the existing pinned-source verifier and normal restore fidelity requirements.

## Planner Research Boundary

T080 directly addresses the #85 model-side decision boundary "Are value targets semantically aligned with the internal states where Search v2 uses the value head?"

It must not silently expand into feature engineering or new training. Its purpose is to decide whether the current value target is answering the same question that Search v2 asks.