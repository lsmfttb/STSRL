# T045: Post-T044 Failure Analysis And Guidance Path Selection

## Objective

Diagnose why the T043-assisted model evidence did not improve T044
de-assisted fixed-cohort outcomes, and produce a reviewable next-path
recommendation.

This task does not try to improve controller strength. It answers whether the
current failure is best explained by a weak model, late root-only search
integration, noisy teacher labels, assisted-to-de-assisted distribution
mismatch, or action-space/fallback problems.

## Current Main Baseline

T043 added assisted Oracle teacher scale-up, assisted trainer-input bridge
support, public student diagnostic checkpoint metadata, and calibration
grouping by assistance level, act, room type, encounter, and distribution
kind.

T044 added `de-assisted-fixed-cohort-comparison-v1` and compared identical
restored starts across baseline Oracle-like search,
`model_guided_oracle_search_v2`, a raw checkpoint-policy diagnostic
controller, and a scripted public baseline. The accepted `assist_hp50` smoke
comparison reported 23W/15L for both baseline search and model-guided search,
11W/27L for raw checkpoint policy, and 19W/19L for the scripted baseline. The
accepted evidence did not show model-guided search improvement over baseline
and did not promote any controller.

Current model-guided Oracle-like search still applies public checkpoint scores
only after the native hidden-state `battle_search` has finished. The current
native API does not accept model priors for root allocation, learned leaf
values, or model callbacks.

## Dependencies

- T043 is complete.
- T044 is complete.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts, not temporary worktree
leftovers:

- one or more T044 `de-assisted-fixed-cohort-comparison-v1` JSONL artifacts;
- the T043 checkpoint, trainer-input, bridge, teacher, calibration, and
  manifest identities used by those comparisons, either embedded in the T044
  report provenance or supplied as explicit paths;
- optional T035/T029 comparison artifacts only as historical contrast, never
  as replacements for T044 evidence.

The primary output is a versioned
`post-t044-failure-analysis-report-v1` JSON report, plus a concise formatted
summary. Generated reports remain under ignored `artifacts/` paths unless a
small fixture is needed for tests.

If a required T043/T044 input is unavailable, the task must fail closed or
report the missing artifact identity explicitly. If an existing artifact lacks
a field needed for one diagnostic, that diagnostic is marked unavailable with
the exact missing field; the implementation must not infer hidden information
or reconstruct simulator mechanics.

This task must not generate new large source pools, teacher datasets,
checkpoints, or restored fixed-cohort evaluations. If a reviewer chooses to
regenerate T043/T044 input artifacts, the PR must report the regeneration
commands, worker/shard counts, record ranges, wall-clock costs, and hashes per
the source task contracts.

## Scope

- Add an offline analysis workflow that consumes T044 comparison artifacts and
  linked T043 provenance.
- Report model-guided search override rate relative to baseline Oracle-like
  search where per-decision selected-action evidence is available.
- Report override outcome deltas on matched restored starts, including battle
  win/loss, terminal absolute HP, potion deltas, and structured resource
  status.
- Analyze raw checkpoint-policy failure modes relative to the scripted
  baseline by available action kind, card/action category, target usage,
  end-turn choice, potion action, block/attack/scaling proxy, encounter, room
  type, act, and assistance level.
- Analyze model score alignment with teacher/search evidence, including
  top-1/top-3 agreement, policy entropy, calibration metrics, whether the
  model top action lands in native top-k root actions, and whether model
  probability concentrates on unvisited or low-value root actions, where the
  current artifacts expose those fields.
- Stratify all headline diagnostics by source distribution, assistance level,
  act, room type, encounter id, and ordinary/elite/Boss room category where
  available.
- Emit a failure taxonomy with evidence weights or counts for:
  `model-too-weak`, `integration-too-late`, `teacher-label-noisy`,
  `distribution-mismatch`, and `action-space/fallback-issue`.
- Recommend the next task path based on the taxonomy, such as a native
  root-prior allocation surface, root-prior guided comparison, assisted
  training repair, or non-combat ranker scoping.

## Out Of Scope

- New source generation, teacher collection, checkpoint training, or fixed
  cohort evaluation.
- New controller behavior or changes to action selection.
- Native `sts_lightspeed` API changes.
- Normal-information belief search or T034 implementation.
- Controller promotion, live-game validation, or broad A20 training claims.
- Treating assisted data as natural A20 performance evidence.

## Design Constraints

- Preserve the existing information-regime labels. T043/T044 Oracle-like
  search evidence remains `full_simulator_state_oracle_like`.
- Keep baseline search, model-guided search, raw checkpoint policy, and
  scripted baseline arms separate. Do not collapse them into one aggregate.
- Preserve T043/T044 artifact identities, cohort identities, source identities,
  checkpoint identities, and assistance provenance in the report.
- Missing data must be explicit. Do not guess teacher rows, hidden states,
  action identities, target choices, or resource outcomes.
- Analyze source identity coverage separately from repeated decision rows or
  battle rows.
- CLI changes, if needed, must keep parsing/routing in `cli.py` or
  `commands/`, with reusable analysis logic below the command layer.
- Any WSL simulator work used only to regenerate prerequisite artifacts must
  follow the per-stage sharding and worker-reporting rule from
  `docs/tasks/README.md`.

## Deliverables

- A versioned `post-t044-failure-analysis-report-v1` artifact schema, writer,
  reader, validator, and formatted summary.
- An offline command or command workflow for producing the report from explicit
  T044 comparison paths and linked T043 provenance.
- Focused tests with small fixtures for matched-source validation, missing
  fields, override accounting, raw-policy failure grouping, taxonomy
  assignment, stratified summaries, and no-promotion language.
- Documentation or help text describing required inputs and artifact identity
  reporting.
- A PR report with consumed artifact paths, SHA-256 hashes, generated report
  path/hash, unavailable diagnostics, taxonomy outcome, and recommended next
  task path.

## Acceptance Criteria

- The command rejects unsupported schemas, source/cohort mismatches, missing
  required controller arms, malformed artifact provenance, and mixed
  information regimes.
- The report includes model-guided versus baseline override accounting, or an
  explicit unavailable status naming the exact missing per-decision fields.
- Outcome deltas compare only matched restored starts and keep win/loss,
  terminal HP, potion deltas, and structured resource status separate.
- Raw checkpoint-policy diagnostics are separated from model-guided search
  diagnostics and are compared against the scripted baseline where both arms
  are present.
- Model/teacher/search alignment diagnostics preserve top-k, entropy,
  calibration, and native-root membership evidence where available, and mark
  unavailable fields explicitly.
- All headline metrics are stratified by assistance level and structural
  metadata where available; no single average is presented as sufficient.
- The failure taxonomy reports counts, proportions, or explicit unavailable
  reasons for all five categories.
- The recommendation section chooses one or more next paths and explains why
  the evidence supports them. It must not mark any follow-up as implemented or
  promoted.
- No new controller, training run, broad-training claim, normal-information
  claim, live-game claim, or A20 performance claim is introduced.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T045 tests,
task-doc checks, and `git diff --check`.

The task should not require new WSL simulator execution. If the PR regenerates
or extends T043/T044 artifacts for analysis input, it must first run the pinned
source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Any regenerated teacher, restored-evaluation, or comparison stage must report
its shard count, worker count, record ranges, wall-clock cost, artifact hashes,
and any lower-worker or single-worker reason.

## Legacy Reference

Consult T025--T029 for telemetry and model-guided search comparison patterns,
T035 for the v2 root-only model-guided comparison, T043 for assisted
teacher/checkpoint provenance, and T044 for de-assisted fixed-cohort
comparison artifacts. Do not reuse old smoke checkpoints, cohorts, or local
artifacts without explicit current-schema provenance.

## PR Report

The PR must report task ID, consumed artifact identities, generated analysis
artifact identity, schema versions, controller arm labels, source/cohort match
status, unavailable diagnostics, stratified metric summaries, failure taxonomy
counts/proportions, recommended next path, verification commands and results,
known limitations, and documentation impact.
