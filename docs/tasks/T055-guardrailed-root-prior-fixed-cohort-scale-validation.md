# T055: Guardrailed Root-Prior Fixed-Cohort Scale Validation

## Objective

Scale-validate the T054 guardrailed root-prior allocation variant on the two
retained T048 fixed cohorts, and decide whether the repaired variant should
advance to a complete-run reachability task, another diagnostic, or be stopped.

This task is a validation pass, not a tuning pass. It asks whether the repaired
guardrail preserves the positive T048 fixed-cohort root-prior signal while
respecting the limitation found in T054's Act-2+ subset.

## Current Main Baseline

T054 is complete. It added
`guardrailed_root_prior_guided_oracle_search_v1`, preserved the existing
`root_prior_guided_oracle_search_v1`, and produced
`t054-guardrailed-root-prior-repair-report-v1` on the retained T052
Boss/later-act fixed diagnostic cohort. The accepted result was:

- all 93 T052 records: baseline Oracle search 4W/89L, post-search
  `model_guided_oracle_search_v2` 4W/89L, existing root-prior 3W/90L, and
  guardrailed root-prior 4W/89L;
- T053 disagreement records `53`, `54`, `55`, and `87`: baseline 3W/1L,
  post-search 3W/1L, existing root-prior 2W/2L, and guardrailed root-prior
  3W/1L;
- Boss-only records: baseline 1W/87L, post-search 1W/87L, existing root-prior
  1W/87L, and guardrailed root-prior 2W/86L;
- Act-2+ records: baseline 3W/2L, post-search 3W/2L, existing root-prior
  2W/3L, and guardrailed root-prior 2W/3L.

T054 recommended exactly one next task: scale the repaired variant. T054 did
not claim controller promotion, live-game strength, natural A20 performance,
broad-training readiness, normal-information strength, or final-agent status.

T048 remains the accepted larger restored-battle root-prior scale evidence. It
ran two matched fixed cohorts at equal native root budget 20:

- current T046-compatible 8-record cohort: baseline Oracle 5W/3L, post-search
  5W/3L, existing root-prior 6W/2L;
- assist_0 runs1000 21-record cohort: baseline Oracle 11W/10L, post-search
  11W/10L, existing root-prior 13W/8L.

## Dependencies

T054, T048, T047, T046, T044, T043.

## Inputs And Artifacts

Required explicit T054 inputs:

- `artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/t054-guardrailed-root-prior-repair-report.json`
  - sha256:
    `91f9e9b63b2f104a092a2a48dc1a3c4cc279f63300b0e097ba116fd80e601fec`
  - schema: `t054-guardrailed-root-prior-repair-report-v1`
- `artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/t054-guardrailed-comparison.jsonl`
  - sha256:
    `b588d1d0f648c07d2fbcb1067a9fdea385ce90676e6c3ecd0eda6f61dbc7627d`
  - schema: `root-prior-guided-search-comparison-v1`
- `artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/t054-retention-manifest.json`
  - sha256:
    `61ea735d6c1a31be14ecdc9daad433b18e2c0445ee42f474a2e55dcca957e5d3`
  - schema: `t054-retention-manifest-v1`

Required T048 reference reports:

- `artifacts/t048-root-prior-guided-scale-up-pr/current-t046-full8-budget20-root-prior-comparison.jsonl`
  - sha256:
    `d9d441f75d21a43aea8884f234f06de819060a2f6f1c421ba84ab23a719efb98`
  - cohort identity: `875ea52e3df4cb93`
  - record range: `0:8`
- `artifacts/t048-root-prior-guided-scale-up-pr/assist0-runs1000-full21-budget20-root-prior-comparison.jsonl`
  - sha256:
    `5807c4255c97a5018e189198180435e077b4d2698b66f6227e9580cb845cb398`
  - cohort identity: `a336ffb1fda9ed7e`
  - record range: `0:21`

Required T048 cohort and checkpoint inputs:

- `artifacts/t047-root-prior-guided-smoke-pr45/current-t046-source/t047-current-t046-a20-seed1-3-fixed-cohort.jsonl`
  - sha256:
    `f336492a7f3b4d9c74b60a636fea54905e6e685025c9e34f174bcfa076b132c3`
  - byte count: `3954322`
- `artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt`
  - sha256:
    `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`
  - byte count: `386717`
- `artifacts/t044-de-assisted-comparison-pr/runs1000-fixed-cohorts/assist_0-runs1000-fixed-cohort.jsonl`
  - sha256:
    `4ee0eb125ac37e870f0f2c950290b131f4693185c60b6c71cd46b5265a4d0037`
  - byte count: `16265964`
- `artifacts/t044-de-assisted-comparison-pr/t043-main-runs1000-assist_0-s4/t043-main-runs1000-assist_0-s4-checkpoint.pt`
  - sha256:
    `ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3`
  - byte count: `387219`

The accepted T048 runner scripts under
`artifacts/t048-root-prior-guided-scale-up-pr/` document how the two reference
cohorts were evaluated. They are reference evidence, not executable source for
this task; T055 must consume the stable artifact paths above explicitly.

The PR must write current-schema T055 outputs under an ignored stable path such
as:

```text
artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/
```

Required generated artifacts:

- a versioned `t055-guardrailed-root-prior-scale-validation-report-v1` JSON
  report;
- restored-battle comparison JSONL artifacts for both retained T048 cohorts;
- shard logs, merge metadata, and any command wrappers needed to reproduce the
  comparison;
- a lightweight retention manifest with schema ids, paths, byte counts,
  SHA-256 hashes, commands, worker/shard counts, cohort ranges, wall-clock
  costs, retention reason, downstream consumers, and deletion conditions.

GB-scale raw artifacts stay out of Git. If any raw comparison or shard output
is retained for downstream work, the manifest must place it under the stable
ignored path above and state when it may be deleted.

## Scope

- Reuse the T054
  `guardrailed_root_prior_guided_oracle_search_v1` behavior without retuning
  its allocation guardrail.
- Run a restored-battle fixed-cohort comparison on both retained T048 cohorts
  with required arms:
  - baseline Oracle search;
  - post-search `model_guided_oracle_search_v2`;
  - existing `root_prior_guided_oracle_search_v1`;
  - `guardrailed_root_prior_guided_oracle_search_v1`.
- Keep equal configured native root budget 20, root selection
  `highest_mean`, A20, simulator step cap 200, and the T048 cohort/checkpoint
  pairing for each cohort.
- Verify the accepted T048 and T054 input hashes before evaluation or report
  generation.
- Report each cohort separately and only then report a clearly labeled
  aggregate across the two T048 cohorts.
- Compare the guardrailed variant against the existing root-prior arm,
  baseline Oracle search, post-search model-guided v2, and the accepted T048
  three-arm reference outcomes.
- Preserve distribution tags and cohort identities. The current T046-compatible
  cohort and assist_0 runs1000 cohort must not be collapsed into a natural A20
  performance claim.
- Report per-record outcome changes, terminal status, terminal absolute HP,
  structured resource status, restore/truncation/controller-problem status,
  decision counts, simulator steps, wall-clock costs, root-prior allocation
  telemetry, guardrail telemetry, and unavailable diagnostics.
- Recommend exactly one next task: repaired-variant complete-run reachability,
  another fixed-cohort diagnostic, abandon the guardrail path, or publish a
  different blocked path.

## Out Of Scope

- Changing T054 guardrail behavior or tuning its parameters.
- Controller promotion, default-controller replacement, live-game validation,
  broad A20 teacher/checkpoint refresh, checkpoint training, non-combat ranker
  changes, or normal-information belief search.
- Complete-run source collection or reachability scale-up.
- Replacing or resampling the retained T048 cohorts.
- Implementing Slay the Spire mechanics locally.
- Using outcome labels, cohort indices, hidden future information, or
  unrevealed encounter information as online decision features.

## Design Constraints

- All compared search arms remain `full_simulator_state_oracle_like`.
- The repaired variant may use public checkpoint policy probabilities only as
  root allocation hints. Final action selection must stay governed by native
  search result semantics.
- Existing `root_prior_guided_oracle_search_v1` and
  `guardrailed_root_prior_guided_oracle_search_v1` must remain explicitly
  constructible with distinct controller provenance.
- Fail closed on unsupported schemas, SHA-256 mismatches, cohort identity
  mismatches, checkpoint identity mismatches, missing required arms, mixed
  information regimes, malformed allocation metadata, restore failures that
  invalidate comparison, or missing required provenance.
- Missing diagnostics must be explicit. Do not infer step-level causal effects
  or selected-action equivalence unless the retained telemetry supports that
  comparison.
- Real `sts_lightspeed` restored-battle comparison gates must run through WSL
  and follow the repository worker/shard rule. Use 8 workers/shards for the
  8-record current T046-compatible cohort and 16 workers/shards for the
  21-record assist_0 runs1000 cohort unless the PR reports a concrete resource
  or tooling reason.

## Deliverables

- A T055 command workflow or report command that consumes explicit T048/T054
  artifact paths, verifies their identities, runs or finalizes the two
  four-arm comparisons, and writes the T055 report/manifest.
- Any generic comparison support needed to include the T054 guardrailed arm on
  non-T052 fixed cohorts without weakening the older T047/T048/T052 report
  contracts.
- A current-schema T055 report writer/validator and formatted summary.
- Focused tests for input hash fail-closed behavior, required-arm validation,
  cohort identity checks, separate cohort and aggregate summaries,
  guardrail-telemetry aggregation, accepted T048 reference comparison, exact
  one-next-task recommendation, and no-promotion wording.
- Retained T055 artifacts and PR evidence with exact paths, hashes,
  worker/shard counts, commands, wall-clock costs, cohort ranges, and known
  limitations.

## Acceptance Criteria

- The T055 report verifies all required T048 and T054 input artifact hashes
  before producing success output.
- Both retained T048 cohorts are evaluated over their full record ranges:
  `0:8` for current T046-compatible and `0:21` for assist_0 runs1000.
- Every per-record and aggregate summary keeps the four required arms separate.
- Baseline Oracle, post-search model-guided v2, existing root-prior, and
  guardrailed root-prior all use equal configured native root budget 20 within
  each cohort.
- The report states whether the guardrailed variant preserved, improved,
  regressed, or changed the accepted T048 root-prior advantage on each cohort
  and on the labeled aggregate.
- The report separately compares guardrailed outcomes against baseline Oracle
  search and post-search `model_guided_oracle_search_v2`.
- Restore failures, truncations, controller errors, malformed allocation
  metadata, source/cohort mismatches, or mixed information regimes are not
  silently averaged into success claims.
- Guardrail configuration and allocation telemetry are present for the
  guardrailed arm.
- The recommendation section names exactly one next task and does not claim
  controller promotion, live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, or final-agent
  status.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T055 tests,
relevant T054/root-prior comparison regression tests, task-doc checks, and
`git diff --check`.

Run the WSL restored-battle comparisons against the retained T048 cohorts with
explicitly reported commands, Python/native runtime paths, worker and shard
counts, record ranges, wall-clock costs, generated artifact paths, byte
counts, and SHA-256 hashes.

Required WSL stages by default:

- current T046-compatible cohort: record range `0:8`, 8 workers, 8 shards;
- assist_0 runs1000 cohort: record range `0:21`, 16 workers, 16 shards;
- report/manifest generation may be single-worker only if reported as
  non-simulator artifact aggregation.

If a lower worker count is used for a simulator stage, the PR must report the
concrete resource or tooling constraint and measured wall-clock cost for that
stage.

## Legacy Reference

Consult T048 for the original two-cohort root-prior scale-up command shape,
T054 for the repaired guardrail controller and report contract, T047 for the
root-prior guided comparison workflow, T046 for native root-prior allocation
metadata, and T043/T044 for checkpoint provenance. Selective porting from
current-schema implementations is allowed. Do not port unrelated legacy search,
training, non-combat, or complete-run experiments.

## PR Report

The PR must report task ID, consumed T048/T054 artifact identities, generated
artifact identities, exact commands, worker/shard counts, cohort record ranges,
wall-clock costs, controller arm labels, source/cohort/checkpoint match
status, per-cohort results, labeled aggregate results, accepted T048 reference
comparison, guardrail allocation telemetry, unavailable diagnostics, exactly
one recommended next task, verification commands and results, known
limitations, and documentation impact.
