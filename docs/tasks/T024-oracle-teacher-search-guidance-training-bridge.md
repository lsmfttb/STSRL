# T024: Oracle Teacher Search-Guidance Training Bridge

Status: `DONE` via PR #24, merged 2026-06-25.

## Objective

Add a narrow, auditable bridge from T023 Oracle-like teacher scale-up artifacts
to a search-guidance training artifact and diagnostic checkpoint.

The result must answer a narrow question: can the project convert a reported
T023 teacher budget into public-feature model input with explicit Oracle
teacher policy targets, train a small diagnostic T009-style policy/value
checkpoint under a named smoke or narrow-curriculum override, and preserve
complete target provenance without claiming controller strength.

This task prepares the next model-guided search controller task. It must not
implement a model-guided search controller, run fixed A20 benchmark
comparisons, or describe Oracle-like teacher targets as normal-information
performance evidence.

## Current Main Baseline

Current `main` already has:

- portable A20 natural battle-start source pools from T004;
- fixed structural cohorts from T005;
- explicitly `full_simulator_state_oracle_like` Oracle teacher JSONL artifacts
  from T006;
- optional PyTorch policy/value training plumbing and checkpoint provenance
  from T009;
- public tactical features, public-context artifact propagation, and
  structured resource outcomes from T011/T012/T016/T018;
- stable pinned `sts_lightspeed` source integration from T017/T020;
- A20 coverage reports from T021;
- Oracle teacher dataset reports from T022;
- structured Oracle teacher scale-up manifests and per-budget teacher reports
  from T023.

The current gap is that T009 consumes trainer-input JSONL records whose policy
target is currently the behavior/chosen action, while T023 produces Oracle
teacher rows with separate teacher actions and soft visit targets. Feeding T023
data into T009 without a bridge would either be impossible or would blur
teacher actions into behavior actions. The next model-guided search task needs
a checkpoint with explicit teacher-target provenance before it can be a
reviewable controller dependency.

## Dependencies

- T003, T004, T006, T009, T011, T012, T016, T017, T018, T020, T021, T022, and
  T023 are complete.
- T007 is cancelled and is not a dependency.

## Scope

- Add a focused teacher-to-training workflow under `src/sts_combat_rl/commands/`
  and reusable conversion/validation logic below the command layer.
- Add a CLI entry point for converting a T023 scale-up output into a
  teacher-targeted training artifact, for example:

  ```text
  --oracle-teacher-search-guidance-input SCALEUP_MANIFEST_JSON
  ```

- Add focused options for the workflow, for example:

  ```text
  --oracle-teacher-search-guidance-budget 100
  --oracle-teacher-search-guidance-output TRAINER_JSONL
  --oracle-teacher-search-guidance-target teacher_action_one_hot
  --oracle-teacher-search-guidance-stability-filter none
  --oracle-teacher-search-guidance-checkpoint-output CHECKPOINT_PATH
  --oracle-teacher-search-guidance-epochs 1
  ```

  Exact flag names may be adjusted before implementation only by updating this
  task document. The public behavior must remain the same.

- Load the current T023 `oracle-teacher-scaleup-manifest-v1` manifest.
- Select exactly one generated teacher budget artifact by requested budget.
- Verify that the selected teacher artifact, its T022 report, and the T023
  manifest identities match the files being consumed.
- Load the source natural battle-start pool named by the T023 manifest.
- Restore each selected source start through the current simulator adapter and
  rebuild the public tactical/model-input feature surface from the actual
  pre-decision source state. Do not reconstruct game mechanics in Python.
- Build a current training artifact whose policy target is explicit and
  versioned, for example:

  ```text
  policy_target_kind = oracle_teacher_action_one_hot
  policy_target_source = oracle_teacher_row.teacher_action
  ```

  Optionally support a second explicit target kind for soft visit targets:

  ```text
  policy_target_kind = oracle_soft_visit_distribution
  policy_target_source = oracle_teacher_row.soft_visit_target
  ```

- Preserve behavior/chosen action fields as separate diagnostic fields. If a
  legacy T009 trainer-input shape is extended, migrations must make the old
  behavior-action target explicit rather than silently changing its meaning.
- Preserve structured outcome targets from the matched source pool when
  available. Missing source outcomes must be explicit and must not be guessed
  from current HP or teacher value estimates.
- Preserve public-context status and sanitized public run context. Missing
  public context remains explicit.
- Add or extend optional PyTorch training support so the T009 policy/value
  model can train from the explicit teacher policy target while retaining the
  existing outcome, absolute-current-HP, and structured-resource target heads
  when labels are available.
- Write a versioned bridge report, for example
  `oracle-teacher-search-guidance-bridge-report-v1`, summarizing:

  ```text
  T023 manifest identity
  selected teacher budget and target kind
  selected teacher artifact and T022 report identities
  source pool identity and restore counts
  trainer artifact identity
  teacher row count and emitted trainer row count
  skipped rows and reasons
  policy target coverage
  structured outcome target availability
  public-context availability
  optional checkpoint identity
  training gate override used
  raw diagnostic metrics
  information-regime and evidence-boundary summary
  problems and warnings
  ```

- Emit a deterministic human-readable stderr summary suitable for PR evidence.

## Out Of Scope

- Model-guided search controller implementation.
- Fixed A20 benchmark comparison between controllers.
- Broad neural training or declaring the broad-training gate satisfied.
- Treating Oracle teacher actions as normal-information labels or promoted
  policy behavior.
- Normal-information belief search or public-consistent hidden-future sampling.
- New `sts_lightspeed` native APIs or native game-code changes.
- Constructed supplement teacher conversion unless a future task defines a
  restorable constructed-source teacher boundary.
- Large-scale training runs or checking generated trainer datasets,
  checkpoints, teacher artifacts, reports, native artifacts, game files, jars,
  mods, save files, or large binaries into the repository.
- Gymnasium, Stable-Baselines3, or new mandatory training dependencies.

## Design Constraints

- The actual game is the final mechanics authority. `sts_lightspeed` remains
  the current large-scale simulator substrate and authoritative simulator for
  this workflow; do not reimplement game mechanics in Python.
- Real simulator restore/conversion gates run through WSL.
- All teacher-derived policy targets in this task are
  `full_simulator_state_oracle_like` supervision. They may train a diagnostic
  search-guidance checkpoint but must never be silently reported as
  normal-information performance.
- Teacher action, soft visit target, behavior action, and model policy target
  must remain separately inspectable after serialization, migration, training,
  and checkpoint loading.
- Policy target kind and target source must be explicit in the training
  artifact, bridge report, and checkpoint provenance.
- If the current trainer-input schema is extended, legacy reader migrations
  must preserve old behavior-action semantics and current writers must emit
  only the new current schema.
- Broad training remains fail-closed. Any smoke or narrow-curriculum training
  must use a named override and report that it is not broad-training evidence.
- Stable source identity must continue to use source checkpoints or
  source-run/battle identity; repeated rows from the same source cannot count
  as new source coverage.
- Source selection, target filtering, and stability filtering may use only
  rule-defined metadata and T023 stability statistics. Do not filter by
  hand-written deck quality, relic quality, route quality, or apparent
  winnability.
- CLI parsing remains thin. Workflows live in `src/sts_combat_rl/commands/`;
  reusable conversion, schema, validation, and formatting logic lives below
  that layer.
- PyTorch remains optional behind the existing `train` dependency group.

## Deliverables

- A reusable teacher-to-search-guidance training conversion module below the
  command layer.
- A command workflow under `src/sts_combat_rl/commands/`.
- CLI parser, validation, and routing for the bridge command and options.
- A current training artifact schema or a current trainer-input schema upgrade
  that explicitly represents teacher policy targets without overloading
  behavior actions.
- Sequential migrations and regression fixtures for any trainer-input schema
  upgrade.
- Updated T009 optional PyTorch training/evaluation/checkpoint provenance to
  consume and report the explicit policy target kind.
- A current machine-readable bridge report schema with schema id/version,
  input identities, selected budget, target kind, conversion counts, restore
  evidence, target availability, optional checkpoint identity, raw diagnostics,
  evidence boundary, warnings, and problems.
- Deterministic human-readable stderr formatting.
- Focused unit tests and CLI tests covering target-kind selection, artifact
  identity checks, row conversion, schema migration, training target selection,
  checkpoint provenance, invalid inputs, and deterministic report output.
- A WSL smoke-scale PR evidence run that converts a T023 smoke artifact and, if
  PyTorch is available, writes a one-epoch diagnostic checkpoint outside the
  repository or under ignored artifact paths.

## Acceptance Criteria

- The bridge command loads a current T023 scale-up manifest and selected
  per-budget teacher artifact.
- The command fails closed if the selected budget is absent, the teacher
  artifact SHA-256 does not match the manifest, the T022 report SHA-256 does
  not match the manifest, the source pool identity is missing, or the selected
  teacher rows cannot be linked to source pool records.
- Restored source states rebuild the public tactical and legal-action feature
  surface without local mechanics reconstruction.
- Teacher targets are matched by occurrence-safe legal-action identity. Index
  only, label only, or arbitrary fallback matching is forbidden.
- Teacher action, soft visit target, behavior action, and policy target remain
  distinct fields in serialized artifacts and checkpoint provenance.
- Legacy trainer-input artifacts still migrate and train with the behavior
  one-hot target explicitly reported as the target kind.
- The generated teacher-target training artifact round-trips deterministically
  and passes model-input packing/preflight checks.
- Stable source identity, distribution kind, sampling component, public-context
  status, and structured outcome status survive conversion.
- Missing public context or missing structured outcomes are explicit problems
  or warnings according to existing T009/T012 contracts; they are not guessed.
- A one-epoch smoke or narrow-curriculum training run can write a diagnostic
  checkpoint when the named override is supplied and PyTorch is installed.
- The checkpoint records exact trainer artifact SHA-256 provenance, target
  kind, target source, Oracle-like information-regime counts, and broad-training
  gate status.
- The bridge report states that the checkpoint and trainer data are
  `full_simulator_state_oracle_like` teacher-supervision artifacts, not
  normal-information, live-game, broad-training, or controller-strength
  evidence.
- The implementation does not implement model-guided search, fixed benchmark
  comparison, normal belief search, native simulator changes, or prohibited
  dependencies.

## Required Verification

Run the standard local gates:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Run focused tests added or touched by the task, including bridge schema,
trainer-input migration, teacher target matching, model-input packing,
training target selection, checkpoint provenance, invalid artifact identities,
CLI validation, and deterministic report formatting.

Run the source verifier before WSL evidence:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run a smoke-scale WSL chain. Exact output paths may differ, but the PR must
include exact commands and summaries:

```powershell
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; rm -rf /tmp/stsrl-t024; mkdir -p /tmp/stsrl-t024; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/stsrl-t024/a20-pool.jsonl --sim-seed 1 --sim-episodes 10 --sim-ascension 20 --sim-steps 300 --battle-start-sample-count 32 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-battle-start-coverage /tmp/stsrl-t024/a20-pool.jsonl --a20-coverage-output /tmp/stsrl-t024/coverage.json --battle-start-restore-limit 0 --battle-start-sample-count 32 --pytorch-gate-required-ascensions 20 --pytorch-gate-required-acts 1 2 3 4 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-oracle-teacher-scaleup /tmp/stsrl-t024/a20-pool.jsonl --oracle-teacher-scaleup-output-dir /tmp/stsrl-t024/teacher-scaleup --oracle-teacher-scaleup-budgets 20 50 100 --oracle-teacher-scaleup-source-limit 32 --oracle-teacher-scaleup-seed 1 --oracle-teacher-scaleup-coverage-report /tmp/stsrl-t024/coverage.json --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --oracle-teacher-search-guidance-input /tmp/stsrl-t024/teacher-scaleup/oracle-teacher-scaleup-manifest.json --oracle-teacher-search-guidance-budget 100 --oracle-teacher-search-guidance-output /tmp/stsrl-t024/teacher-guidance-trainer.jsonl --oracle-teacher-search-guidance-target teacher_action_one_hot --oracle-teacher-search-guidance-stability-filter none --oracle-teacher-search-guidance-report-output /tmp/stsrl-t024/teacher-guidance-report.json --log-file -"
```

If PyTorch is available in the environment, also run a one-epoch diagnostic
training command over the generated trainer artifact using a named smoke or
narrow-curriculum override. The command may be integrated with the bridge
workflow or may reuse the existing T009 training command after the conversion
step. The PR must include the exact command and clearly report that the
checkpoint is diagnostic only.

The final bridge report should exit zero for a valid under-covered smoke-scale
teacher artifact while clearly reporting:

- selected budget and policy target kind;
- teacher rows consumed, trainer rows emitted, skipped rows, and skip reasons;
- restore count and restore failures;
- policy target coverage;
- structured outcome target availability;
- public-context availability;
- trainer artifact identity;
- optional checkpoint identity and raw diagnostic metrics;
- broad-training gate status and override;
- that the data/checkpoint are `full_simulator_state_oracle_like`
  teacher-supervision artifacts and not normal-information, live-game,
  broad-training, or controller-strength evidence.

## Legacy Reference

Consult current merged code and tests for T006, T009, T011, T012, T016, T018,
T021, T022, and T023. The legacy integration branch may be inspected only for
conversion or training-target ideas, not wholesale porting.

## PR Report

The pull request must include:

- task ID and link to this document;
- bridge report schema id/version;
- trainer artifact schema or trainer-input schema upgrade summary;
- CLI interface summary;
- exact local and WSL verification commands and results;
- source manifest identity and pinned `sts_lightspeed` commit used for WSL
  evidence;
- T023 manifest identity, selected budget, selected teacher artifact identity,
  selected T022 report identity, and source pool identity;
- policy target kind, target source, stability filter, consumed row count,
  emitted trainer row count, skipped row counts and reasons;
- restore, public-context, structured-outcome, and target-coverage summaries;
- trainer artifact SHA-256 and optional checkpoint SHA-256;
- raw training diagnostics if a checkpoint is written;
- explicit broad-training gate and override status;
- explicit statement that teacher-derived targets and checkpoints are
  `full_simulator_state_oracle_like` supervision and are not
  normal-information, live-game, broad-training, or controller-strength
  evidence;
- compatibility notes for existing trainer-input artifacts, T009 checkpoints,
  and T006/T022/T023 artifacts;
- legacy files consulted, if any;
- known limitations and follow-up recommendations for model-guided search
  controller integration, fixed A20 benchmark reporting, broader A20 data
  collection, and normal-information search groundwork.
