# T056: Post-T055 Root-Prior Path Selection

## Objective

Convert the negative T055 guardrailed root-prior scale result into a
current-schema evidence synthesis and choose one non-guardrail next path.

This task closes the T054/T055 guardrail branch. It does not try to improve
controller strength. It decides whether the next branch should investigate the
existing root-prior signal, repair assisted/de-assisted training evidence,
improve source generation or reachability, or publish a blocked path.

## Current Main Baseline

T048 remains the accepted positive restored-battle root-prior scale evidence.
At equal native root budget 20, the existing
`root_prior_guided_oracle_search_v1` arm improved over baseline Oracle search
and post-search `model_guided_oracle_search_v2` on both retained fixed cohorts:

- current T046-compatible 8-record cohort: baseline 5W/3L, post-search 5W/3L,
  existing root-prior 6W/2L;
- assist_0 runs1000 21-record cohort: baseline 11W/10L, post-search 11W/10L,
  existing root-prior 13W/8L.

T052 then found the later-act/Boss diagnostic regression on T051 natural
starts: baseline and post-search were 4W/89L overall, while existing
root-prior was 3W/90L. The five-record Act-2+ subset was 3W/2L for baseline
and post-search versus 2W/3L for root-prior. T053 attributed the available
evidence to four disagreement records while marking exact selected-action
comparison unavailable. T054 added the guardrailed variant and repaired the
T052 overall and Boss-only regression against existing root-prior, but did not
repair the Act-2+ gap.

T055 is complete. It scale-validated the T054
`guardrailed_root_prior_guided_oracle_search_v1` variant on the retained T048
fixed cohorts. The accepted stable report is:

```text
artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/t055-guardrailed-root-prior-scale-validation-report.json
sha256: 0e365f76fcde88d81917b587ae162843488527dd7b422a43998ab24a069cae04
schema: t055-guardrailed-root-prior-scale-validation-report-v1
```

T055 results:

- current T046-compatible 8-record cohort: baseline 5W/3L, post-search 5W/3L,
  existing root-prior 6W/2L, guardrailed root-prior 6W/2L;
- assist_0 runs1000 21-record cohort: baseline 11W/10L, post-search 11W/10L,
  existing root-prior 13W/8L, guardrailed root-prior 12W/9L;
- labeled 29-record aggregate: baseline 16W/13L, post-search 16W/13L,
  existing root-prior 19W/10L, guardrailed root-prior 18W/11L.

The T055 recommendation is exactly one item: abandon the guardrail path. T055
is restored-battle Oracle-like diagnostic evidence only. It does not promote a
controller, prove complete-run reachability, open broad training, validate
normal-information search, or validate live-game strength.

## Dependencies

T055, T054, T053, T052, T051, T050, and T048.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts from stable ignored artifact
paths, not disposable review-worktree outputs.

Required T055 inputs:

- `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/t055-guardrailed-root-prior-scale-validation-report.json`
  - sha256:
    `0e365f76fcde88d81917b587ae162843488527dd7b422a43998ab24a069cae04`
  - schema: `t055-guardrailed-root-prior-scale-validation-report-v1`
- `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/t055-retention-manifest.json`
  - sha256:
    `f1f7692fdc9baca2218dcc68e954e0e0ebdc322bf27dc2654387b52fb8cde787`
  - schema: `t055-retention-manifest-v1`
- `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/current-t046-full8-budget20-guardrailed-comparison.jsonl`
  - sha256:
    `1580968ffd592433d838c3dde780148e43a33c145079f8a332dfcb1a2a9b0246`
- `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/assist0-runs1000-full21-budget20-guardrailed-comparison.jsonl`
  - sha256:
    `7a96015ad103cb6c06d092fd2bf03d7b194cef12d3053808bc444b649ae994da`

Required upstream fixed-cohort and repair inputs:

- T048 current T046-compatible comparison:
  `artifacts/t048-root-prior-guided-scale-up-pr/current-t046-full8-budget20-root-prior-comparison.jsonl`
  - sha256:
    `d9d441f75d21a43aea8884f234f06de819060a2f6f1c421ba84ab23a719efb98`
- T048 assist_0 runs1000 comparison:
  `artifacts/t048-root-prior-guided-scale-up-pr/assist0-runs1000-full21-budget20-root-prior-comparison.jsonl`
  - sha256:
    `5807c4255c97a5018e189198180435e077b4d2698b66f6227e9580cb845cb398`
- T052 result summary:
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-result-summary.json`
  - sha256:
    `1207ae0e93fa6f857add7dbaa553c3d92c86391772e842ce1e6bd08b55d97fe5`
- T053 failure-analysis report:
  `artifacts/t053-t052-root-prior-allocation-failure-analysis-pr/t053-root-prior-allocation-failure-analysis-report.json`
  - sha256:
    `73a1d153adce9782cafaf1caddb3fa0ddad2fafe33e653d88808875397832a73`
- T054 guardrail repair report:
  `artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/t054-guardrailed-root-prior-repair-report.json`
  - sha256:
    `91f9e9b63b2f104a092a2a48dc1a3c4cc279f63300b0e097ba116fd80e601fec`

Required reachability context inputs:

- T050 reachability report:
  `artifacts/t050-root-prior-reachability-scaleup-pr/reachability-report.json`
  - sha256:
    `3ba6d2d5250ca454db43172f887d9f733d961c9aad91a090ba49bf1fb8293359`
- T050 retention manifest:
  `artifacts/t050-root-prior-reachability-scaleup-pr/t050-retention-manifest.json`
  - sha256:
    `74a7390d40e6ffa5c993ed23a9ac782b9267403cef7de92dda31719683b6ea49`
- T051 reachability report:
  `artifacts/t051-search-controlled-later-act-source-collection-pr/reachability-report.json`
  - sha256:
    `0e001e38b3a7587dd7f1845a6d3fcfc6541f2056dffd8e4aaa5206053adc3877`
- T051 retention manifest:
  `artifacts/t051-search-controlled-later-act-source-collection-pr/t051-retention-manifest.json`
  - sha256:
    `e2c83ef4892ff74129c3649dc4b1dd52493777b74339f094c5c804e2bbb3d0b9`

The primary output is a versioned
`t056-post-t055-root-prior-path-selection-report-v1` JSON report plus a
concise formatted summary. Generated reports should remain under an ignored
stable path such as:

```text
artifacts/t056-post-t055-root-prior-path-selection-pr/
```

The PR must report generated report path, schema id, byte count, SHA-256 hash,
input artifact identities, command, and unavailable diagnostics.

## Scope

- Add an offline synthesis workflow that consumes the required T048, T050,
  T051, T052, T053, T054, and T055 artifacts without running the simulator.
- Verify required input schemas and SHA-256 hashes before producing success
  output.
- Report a structured evidence ledger that keeps these evidence families
  separate:
  - positive T048 fixed-cohort restored-battle root-prior signal;
  - negative T052 Boss/later-act restored-battle diagnostic signal;
  - T053 disagreement taxonomy and unavailable selected-action diagnostics;
  - bounded T054 guardrail repair result;
  - T055 retained T048 guardrail scale-validation regression;
  - T050/T051 complete-run source reachability and broad-training gate status.
- State explicitly that the T054/T055 guardrail branch is closed for now and
  that guardrailed root-prior complete-run reachability is not the next
  implementation branch.
- Preserve all information-regime labels. The T048/T052/T054/T055 search
  evidence remains `full_simulator_state_oracle_like`.
- Recommend exactly one next task from this non-guardrail set:
  - existing-root-prior allocation or telemetry diagnostic;
  - assisted/de-assisted checkpoint, teacher, or distribution-repair
    diagnostic;
  - source-generation, reachability, or non-combat-driver branch;
  - publish a blocked path that requires maintainer decision before further
    implementation.

## Out Of Scope

- New simulator execution, restored-battle comparison, source collection,
  teacher collection, trainer-input generation, checkpoint training, or
  calibration runs.
- Changing root-prior, guardrailed root-prior, model-guided search, or
  non-combat controller behavior.
- Tuning, extending, promoting, or rerunning the T054 guardrail.
- Publishing guardrailed root-prior complete-run reachability as the next
  implementation branch.
- Controller promotion, default-controller replacement, live-game validation,
  broad A20 teacher/checkpoint refresh, non-combat ranker implementation, or
  normal-information belief search.
- Treating fixed-cohort restored-battle evidence as natural A20 performance.

## Design Constraints

- Fail closed on unsupported schemas, SHA-256 mismatches, missing required
  inputs, mixed information regimes, missing required controller arms,
  malformed comparison summaries, or missing required provenance.
- Missing diagnostics must be explicit. Do not infer hidden state, missing
  selected actions, hidden future information, or causal allocation effects
  absent from the retained artifacts.
- Keep baseline Oracle search, post-search `model_guided_oracle_search_v2`,
  existing root-prior, and guardrailed root-prior separate wherever those arms
  appear.
- Keep current T046-compatible, assist_0 runs1000, Boss-only, Act-2+, source
  generation, and aggregate labels separate. Aggregates may summarize but must
  not replace the labeled distributions.
- CLI modules must remain limited to parsing and routing. Put reusable
  synthesis logic below the command layer.

## Deliverables

- A versioned `t056-post-t055-root-prior-path-selection-report-v1` report
  schema, writer, validator or reader, and formatted summary.
- An offline command or command workflow that consumes explicit artifact paths
  and writes the T056 report.
- Focused tests for input hash checking, required schema validation,
  evidence-family separation, guardrail-branch closure, exactly-one
  recommendation, unavailable diagnostics, and no-promotion wording.
- A PR report with consumed artifact paths and SHA-256 hashes, generated report
  path and hash, selected next path, rejected alternatives, verification
  results, known limitations, and documentation impact.

## Acceptance Criteria

- The T056 report verifies all required input hashes before reporting success.
- The report states the exact T055 recommendation and marks the T054/T055
  guardrail branch closed for now.
- T048 positive fixed-cohort evidence, T052/T053/T054 later-act/Boss evidence,
  T055 guardrail scale evidence, and T050/T051 complete-run reachability
  evidence are reported separately.
- The report does not recommend guardrailed root-prior complete-run
  reachability, another guardrail tuning pass, or controller promotion as the
  next implementation branch.
- The recommendation section names exactly one non-guardrail next path from
  the allowed set in Scope and explains why the evidence supports it.
- The report does not claim live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, final-agent status,
  or default-controller promotion.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T056 tests,
task-doc checks, and `git diff --check`.

T056 should not require WSL simulator execution. If the PR regenerates or
extends any prerequisite artifact, it must report the exact command, worker and
shard counts, record ranges, wall-clock cost, output path, SHA-256 hash, and
why regeneration was necessary. Any regenerated simulator stage must run
through WSL and follow the repository sharding/worker rule.

## Legacy Reference

Consult T045 for path-selection report patterns, T048 for the positive
root-prior fixed-cohort scale evidence, T050/T051 for complete-run
reachability reporting, T052/T053 for later-act/Boss root-prior failure
evidence, and T054/T055 for the guardrail branch and its closure. Do not reuse
old smoke outputs or local worktree artifacts without explicit current-schema
provenance.

## PR Report

The PR must report task ID, consumed artifact identities, generated analysis
artifact identity, schema versions, evidence-family summaries, guardrail
closure status, selected next path, rejected alternatives, unavailable
diagnostics, verification commands and results, known limitations, and
documentation impact.

## Historical Executor Note

T056 remains DONE and its scientific record is unchanged. Its task-specific
executor was retired by T072; executable historical source is available at
`09f58a7352f8dd860c2ed1d7f2b59beacb61d648`.
