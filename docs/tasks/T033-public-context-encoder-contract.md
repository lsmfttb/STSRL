# T033: Public Context Model-Input Encoder Contract

## Objective

Define and implement `public-context-model-input-v1`, a versioned
normal-public model-input encoder for sanitized public run context.

The goal is not a perfect complete-run representation. The goal is a stable,
testable, checkpoint-provenance-validatable v1 contract that lets later assisted
teacher/value training consume explicit long-horizon public context instead of
the current ad hoc compact summary.

## Current Main Baseline

Current `main` preserves sanitized `public-run-context-v1` and ordered public
history through decisions and current artifacts. `ModelInputBatch` carries raw
`public_run_context` dictionaries, and `torch_policy_value.py` currently
derives a small inline context feature vector through
`encode_public_context_features`.

That inline vector is not yet an independent model-input contract. It is not
serialized as a separate `ModelInputBatch` field, it does not carry a
missingness summary, and it is not reusable by trainer-input preflight,
checkpoint semantic validation, assisted-data non-leakage tests, and future
T043 trainer/report workflows as one named public-context schema.

T040--T042 broadened A20 source distributions, but T043 remains blocked until
the model-input boundary can represent public long-horizon context without
leaking assistance provenance or simulator-only hidden state.

## Dependencies

- T016, T030, and T042 are complete.
- T011, T024, T026, and the current T009 PyTorch checkpoint contract remain
  compatibility contracts.

## Inputs And Artifacts

Inputs are committed fixtures and current-schema in-repository test artifacts
that already contain sanitized public context. Tests may build synthetic
current-schema `TrainerInputRecord` or `ModelInputBatch` objects.

A small T042-style assisted fixture may be committed or constructed in tests to
verify assistance non-leakage. Do not consume the retained T042 GB-scale raw
pools, review-worktree leftovers, or local scale artifacts as required inputs.

This task should update current schema writers and migrations where necessary.
Generated artifacts are test fixtures only; no scale WSL artifact is required.

## Scope

- Add a reusable public-context model-input encoder module below
  `src/sts_combat_rl/sim/`, with constants and helpers for:
  - `public_context_feature_schema_id`;
  - `public_context_feature_schema_version`;
  - `public_context_feature_names`;
  - `public_context_feature_size`;
  - `public_context_features`;
  - `public_context_missingness_summary`.
- Build features only from sanitized `public_run_context` and
  `public_context_status`; the encoder must not call simulator objects, inspect
  native checkpoints, read battle-start provenance, or infer hidden state.
- Keep public tactical battle features separate from public context features.
  Prefer adding explicit context-feature fields to `ModelInputBatch` and the
  PyTorch state assembly path instead of appending context values directly into
  `snapshot_features`.
- Replace the inline `torch_policy_value.encode_public_context_features` path
  with the shared encoder or make it a thin compatibility wrapper.
- Preserve current `public-tactical-v2` state/action semantics and model-input
  variable-action layout.
- Encode explicit missingness. Missing context must be unavailable/missing, not
  silently treated as normal zero-valued context.
- Include at least these v1 feature groups where the sanitized context exposes
  them, with missingness flags where it does not:
  - `run_position`: ascension where available, act, floor, room type/screen
    category, battle/Boss/elite/monster indicators where derivable from public
    fields, and visible Act Boss availability/category.
  - `public_resources_numeric`: current HP, max HP, HP ratio, gold, potion slot
    count, occupied potion count, key flags, deck size, relic count, and curse
    count when each field is public and available.
  - `route_context`: current node availability, immediately legal route
    availability, and visible next-room-type counts when the sanitized map
    field provides them. If the map remains unavailable, encode only
    unavailable/missingness; do not reconstruct the map locally.
  - `history_counts`: typed counts from ordered public history such as visited
    monster, elite, Boss, event, shop, rest, and treasure screens/rooms, plus
    public card/relic/potion/key/reward choice categories where available.
  - `recent_public_outcomes`: bounded summaries from the most recent public
    history entries, including battle outcome and public HP/resource deltas
    where available.
  - `identity_summary_v1`: conservative public identity counts derived only
    from sanitized public context fields that are already public and available.
- Add hidden-field firewall tests. Contexts containing forbidden hidden fields
  such as hidden RNG state, draw order, future encounters, hidden second Boss,
  native checkpoints, or simulator objects must fail closed.
- Add assistance non-leakage tests. T042 fields such as assistance level,
  assistance schedule, requested/actual assistance changes, and assisted
  distribution tags may remain in provenance/reporting/sampling metadata, but
  must not appear in normal model-input context features, raw model context, or
  checkpoint public-context feature metadata.
- Thread the context schema id, version, size, and names through trainer-input
  preflight, model-input smoke reports, PyTorch training reports, and checkpoint
  semantic validation/load.

## Out Of Scope

- Broad training, teacher collection, model promotion, or controller
  evaluation.
- T043 assisted teacher data generation.
- T044 de-assisted fixed-cohort evaluation.
- Native simulator projection changes.
- Hidden-future sampling or belief search.
- Local reconstruction of map, encounter, reward, potion, relic, deck, or
  event mechanics.
- Feeding assistance schedule or assisted distribution labels as normal model
  inputs.

## Design Constraints

- Normal-information encoders consume only sanitized public context and
  public-context status.
- Missing native projection payloads remain explicit missingness.
- Legacy artifacts migrate before business logic runs; readers must not guess
  missing context.
- Feature changes that affect checkpoints require explicit semantic contract
  validation on load.
- The model-input batch and checkpoint contract must preserve tactical feature
  schema identity separately from public-context feature schema identity.
- Assistance labels and before/after assistance resources are provenance and
  reporting data only; they are not normal controller inputs.

## Deliverables

- `public-context-model-input-v1` encoder constants, feature names, feature
  packing helpers, missingness summary, and validation helpers.
- `ModelInputBatch` integration with explicit public-context feature fields and
  migration from older batches.
- Trainer-input preflight and model-input smoke reporting that reports context
  feature schema id/version/size and missingness summary.
- PyTorch policy/value integration through the shared context encoder,
  including checkpoint save/load semantic validation for schema id, version,
  size, and feature names.
- Focused tests for schema identity, deterministic packing, missingness,
  hidden-field firewall, assistance non-leakage, legacy/missing context, and
  checkpoint semantic compatibility.

## Acceptance Criteria

- Current model-input packing exposes separate public-context feature fields:
  `public_context_feature_schema_id`,
  `public_context_feature_schema_version`,
  `public_context_feature_size`, `public_context_feature_names`,
  `public_context_features`, and `public_context_missingness_summary`.
- All context features are constructed only from sanitized `public_run_context`
  and `public_context_status`.
- Context-unavailable or legacy records are explicitly marked unavailable or
  fail closed according to the current schema; they are not silently treated as
  ordinary zero-context training rows.
- Hidden-field firewall tests fail closed for forbidden hidden or native-state
  keys.
- Assistance non-leakage tests prove T042 assistance schedule, assistance
  before/after changes, and assisted distribution tags do not enter normal
  model-input features or checkpoint context-feature metadata.
- Checkpoint semantic validation rejects mismatched public-context schema id,
  version, size, or feature names instead of silently loading incompatible
  checkpoints.
- Existing trainer-input artifacts and model-input batch migrations remain
  covered by regression tests.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused
public-context/model-input/checkpoint tests, task-doc checks, and
`git diff --check`.

Required focused checks should include, at minimum:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests\test_battle_agent.py tests\test_torch_policy_value.py tests\test_trainer_input_preflight.py -q
$env:PYTHONPATH='src'; python -m pytest tests\test_task_docs.py -q
git diff --check
```

Real WSL simulator scale gates are not required. If the implementation touches
WSL-facing smoke paths, run the standard WSL smoke/readiness commands and
report them in the PR.

## Legacy Reference

Consult current T011, T016, T024, T026, and T042 code and tests. Historical
plans may inform feature grouping but are not current contracts.

## PR Report

The PR must report task ID, schema id/version, feature groups and feature
size, missingness behavior, hidden-field firewall behavior, assistance
non-leakage evidence, trainer/model/checkpoint compatibility impact,
verification commands, known limitations, and documentation impact.
