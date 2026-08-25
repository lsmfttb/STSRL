# T054: Guardrailed Root-Prior Allocation Repair Experiment

## Objective

Test one versioned guardrailed root-prior allocation variant on the retained
T052 Boss/later-act fixed diagnostic cohort, and determine whether it repairs
the T053 disagreement signal without claiming controller promotion.

The goal is not to tune a final controller. It is to turn T053's allocation
failure analysis into one falsifiable restored-battle experiment before any
larger source collection, training refresh, non-combat branch, or promotion
gate.

## Current Main Baseline

T053 is complete. It added the offline
`t053-root-prior-allocation-failure-analysis-v1` report over the retained T052
artifacts and found four root-prior disagreement records out of 93:

- cohort indices `53`, `54`, `55`, and `87`;
- harmful root-prior records at `53` and `55`;
- one terminal-HP-only/no-op record at `54`;
- one beneficial root-prior record at `87`;
- exact step-level selected-action comparison unavailable because the T052
  telemetry does not expose compatible selected action identities for all arms.

The accepted T053 report is retained at:

```text
artifacts/t053-t052-root-prior-allocation-failure-analysis-pr/t053-root-prior-allocation-failure-analysis.json
```

Accepted T053 report identity:

```text
sha256: 73a1d153adce9782cafaf1caddb3fa0ddad2fafe33e653d88808875397832a73
byte_count: 521106
schema_id: t053-root-prior-allocation-failure-analysis-v1
```

T052 remains the fixed restored-battle diagnostic input. Its retained artifact
root is:

```text
artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/
```

Accepted T052 artifact identities:

- retention manifest `t052-retention-manifest.json`:
  `6830027aa23db10fd4ce3be17dbaf453e04ebbf9326622d23c3c8ff2b56f130e`;
- fixed cohort `t052-fixed-cohort.jsonl`:
  `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`;
- root-prior guided comparison `t052-root-prior-guided-comparison.jsonl`:
  `0cc496e6bddff0e5cecaee5e804d9ff4c89b2498093cb59d3feffbd245bb4a64`;
- result summary `t052-result-summary.json`:
  `1207ae0e93fa6f857add7dbaa553c3d92c86391772e842ce1e6bd08b55d97fe5`.

The baseline T052 result was 4W/89L for baseline Oracle search, 4W/89L for
post-search model-guided v2, and 3W/90L for root-prior guided search. Boss-only
tied at 1W/87L for all arms. The five-record Act-2+ subset was 3W/2L for
baseline and post-search versus 2W/3L for root-prior.

## Dependencies

T053, T052, T048, T047, T046, T043.

## Inputs And Artifacts

Required explicit inputs:

- the accepted T053 report listed above;
- the accepted T052 retention manifest, fixed cohort, root-prior guided
  comparison, and result summary listed above;
- the T043/T044 checkpoint provenance already consumed by the T047/T048/T052
  root-prior guided comparison workflow;
- the pinned `sts_lightspeed` source manifest on current `main`.

The PR must write current-schema T054 outputs under an ignored stable path such
as:

```text
artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/
```

Required generated artifacts:

- a versioned `t054-guardrailed-root-prior-repair-report-v1` JSON report;
- any comparison JSONL, shard reports, logs, or manifests needed to regenerate
  or audit the T054 report;
- a lightweight retention manifest with schema ids, paths, byte counts,
  SHA-256 hashes, commands, worker/shard counts, cohort ranges, and retention
  reason for every retained generated artifact.

GB-scale raw artifacts stay out of Git. If any raw shard output must be kept for
downstream work, the retention manifest must state the downstream consumer and
deletion conditions.

## Scope

- Add one versioned guardrailed root-prior allocation/search variant. The old
  `root_prior_guided_oracle_search_v1` behavior must remain explicitly
  constructible for diagnostics.
- The guardrail may adjust only the public checkpoint-prior-to-root-allocation
  path. It may not use hidden future outcomes, unrevealed encounter
  information, T053 labels as online inputs, or post-hoc knowledge of the
  cohort index.
- Record the guardrail configuration in controller provenance and per-decision
  telemetry, including enough pre/post allocation information to explain how it
  changed native root allocation.
- Run a restored-battle fixed-cohort comparison on the full 93-record T052
  cohort at equal native root budget. Required arms are:
  - baseline Oracle search;
  - post-search `model_guided_oracle_search_v2`;
  - existing `root_prior_guided_oracle_search_v1`;
  - the new guardrailed root-prior variant.
- Compare the guardrailed variant with the existing T052/T053 evidence on:
  - all 93 records;
  - the T053 disagreement indices `53`, `54`, `55`, and `87`;
  - Boss-only records;
  - Act-2+ records.
- Report whether the guardrail fixes, worsens, or leaves unchanged each T053
  disagreement record, including terminal status, terminal absolute HP,
  structured resource status, decision counts, simulator steps, wall-clock
  cost, restore/truncation status, controller problems, root-prior allocation
  telemetry, and unavailable diagnostics.
- Recommend exactly one next task: scale the repaired variant, run another
  diagnostic, abandon the repair path, or publish a different blocked path.

## Out Of Scope

- Controller promotion or default-controller replacement.
- Complete-run source collection, reachability scale-up, live-game validation,
  broad A20 teacher/checkpoint refresh, checkpoint training, or non-combat
  ranker changes.
- Changing baseline Oracle search, post-search model-guided search, T052 input
  artifacts, T053 report semantics, or fixed-cohort selection.
- Implementing Slay the Spire mechanics locally.
- Using T053 disagreement labels as online decision features.

## Design Constraints

- All compared search arms remain `full_simulator_state_oracle_like`.
- Model priors are allocation hints only. Final action selection must stay
  governed by native search result semantics, not by directly choosing the
  checkpoint's top policy action.
- The guardrail must be versioned. Any behavior-affecting change after this
  task requires a new version.
- Preserve action-space configuration, checkpoint provenance, source identity,
  public-context status, structured-outcome/resource status, information
  regime, and controller provenance.
- Fail closed on unsupported T052/T053 schemas, SHA-256 mismatches, source or
  cohort identity mismatches, missing required arms, mixed information regimes,
  malformed allocation metadata, restore failures that invalidate comparison,
  or missing required provenance.
- Missing telemetry must be explicit. Do not guess selected actions, root rows,
  priors, hidden state, or resource outcomes.
- Real `sts_lightspeed` restored-battle comparison gates must run through WSL
  and follow the repository worker/shard rule. On the current 16-logical-core
  maintainer machine, use 16 workers by default unless the PR reports a
  concrete lower-worker resource or tooling reason.

## Deliverables

- A versioned guardrailed root-prior controller/allocation configuration and
  telemetry surface.
- A current-schema T054 repair report schema, writer, reader or validator, and
  formatted summary.
- CLI or command workflow for running the T054 comparison and writing the
  report/manifest from explicit T052 and T053 artifact paths.
- Focused tests covering configuration/provenance, old-version
  constructibility, guardrail telemetry, input hash/schema fail-closed behavior,
  disagreement-index aggregation, subset aggregation, no-promotion wording, and
  report round trip.
- A retained T054 artifact manifest and PR evidence with exact paths, hashes,
  worker/shard counts, commands, wall-clock costs, and known limitations.

## Acceptance Criteria

- The existing root-prior guided controller remains constructible and
  behavior-compatible for existing tests.
- The new guardrailed variant has a distinct versioned controller name and
  complete provenance.
- The T054 command verifies accepted T052 and T053 input hashes before
  analysis/evaluation, or fails closed with a clear mismatch.
- The report evaluates all 93 T052 cohort records and separately reports
  indices `53`, `54`, `55`, and `87`, Boss-only, and Act-2+ subsets.
- Required arms are kept separate in every per-record and aggregate summary.
- The report states whether the guardrail improved, tied, or regressed versus
  existing root-prior guided search, baseline Oracle search, and post-search
  model-guided search at equal configured native root budget.
- The report includes root-prior allocation telemetry for the guardrailed arm,
  and explicitly reports unavailable diagnostics where telemetry cannot support
  a causal statement.
- Restore failures, truncations, controller errors, malformed allocation
  metadata, source/cohort mismatches, or mixed information regimes are not
  silently averaged into success claims.
- The recommendation section names exactly one next task and does not claim
  controller promotion, live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, or final-agent status.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T054 tests,
task-doc checks, and `git diff --check`.

Run the WSL restored-battle T054 comparison on the retained T052 cohort with
explicitly reported 16-worker/16-shard execution by default. The PR must report
the exact command, Python/native runtime paths, worker and shard counts, cohort
record ranges, wall-clock cost, generated artifact paths, byte counts, and
SHA-256 hashes.

If a lower worker count is used, the PR must report the concrete resource or
tooling constraint and measured wall-clock cost for every affected WSL stage.

## Legacy Reference

Consult T046 for native root-prior allocation metadata, T047/T048 for the
root-prior guided comparison workflow, T052 for the retained fixed diagnostic
cohort, and T053 for the disagreement taxonomy. Selective porting from these
current-schema implementations is allowed. Do not port unrelated legacy search,
training, or non-combat experiments.

## PR Report

The PR must report task ID, implemented guardrail version and parameters,
consumed T052/T053 artifact identities, generated artifact identities, exact
commands, worker/shard counts, cohort ranges, wall-clock costs, controller arm
labels, source/cohort match status, all-record results, T053 disagreement-index
results, Boss-only and Act-2+ results, allocation telemetry availability,
unavailable diagnostics, exactly one recommended next task, verification
commands and results, known limitations, and documentation impact.

## Historical Executor Note

T054 remains DONE and its scientific record is unchanged. Its task-specific
executor was retired by T072; executable historical source is available at
`09f58a7352f8dd860c2ed1d7f2b59beacb61d648`.
