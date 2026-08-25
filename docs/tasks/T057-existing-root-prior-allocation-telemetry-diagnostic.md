# T057: Existing Root-Prior Allocation Telemetry Diagnostic

## Objective

Diagnose the existing `root_prior_guided_oracle_search_v1` allocation and
selected-action telemetry after T056, using retained current-schema artifacts
only.

This task does not tune root-prior allocation, revive the T054/T055 guardrail,
run a new simulator comparison, or promote a controller. It determines whether
the current retained telemetry can explain the positive T048 fixed-cohort
signal and the negative T052 Boss/later-act signal, and what exact telemetry
gap blocks the next implementation branch.

## Current Main Baseline

T056 is complete. It produced the stable
`t056-post-t055-root-prior-path-selection-report-v1` artifact:

```text
artifacts/t056-post-t055-root-prior-path-selection-pr/t056-post-t055-root-prior-path-selection-report.json
sha256: f5db1a5f6bcdd99f78051f7b99ad970c76099add59d9655c6cd2abdd2ad6e26e
byte count: 1411522
schema: t056-post-t055-root-prior-path-selection-report-v1
```

T056 closed the T054/T055 guardrail branch and selected exactly one
non-guardrail next path: `existing-root-prior allocation/telemetry diagnostic`.
The retained evidence remains split:

- T048 positive fixed-cohort signal: baseline 16W/13L, post-search 16W/13L,
  existing root-prior 19W/10L across the retained 29-record aggregate;
- T052 later-act/Boss diagnostic: baseline and post-search 4W/89L overall,
  existing root-prior 3W/90L overall, with Act-2+ at 3W/2L for baseline and
  post-search versus 2W/3L for root-prior;
- T053 disagreement analysis: four T052 disagreement records and exact
  all-arm step-level selected-action comparison unavailable;
- T055 guardrail scale validation: guardrail abandoned after regressing by one
  win versus existing root-prior on the assist_0 retained cohort and aggregate;
- T050/T051 complete-run reachability: scarce later-act starts recovered in
  T051 guided arms, but broad training remains closed.

## Dependencies

T056, T055, T053, T052, T048, T046, and T043.

## Inputs And Artifacts

Inputs must be explicit stable ignored artifacts, not disposable review
worktree files.

Required path-selection input:

- `artifacts/t056-post-t055-root-prior-path-selection-pr/t056-post-t055-root-prior-path-selection-report.json`
  - sha256:
    `f5db1a5f6bcdd99f78051f7b99ad970c76099add59d9655c6cd2abdd2ad6e26e`
  - schema: `t056-post-t055-root-prior-path-selection-report-v1`

Required fixed-cohort comparison inputs:

- T048 current T046-compatible comparison:
  `artifacts/t048-root-prior-guided-scale-up-pr/current-t046-full8-budget20-root-prior-comparison.jsonl`
  - sha256:
    `d9d441f75d21a43aea8884f234f06de819060a2f6f1c421ba84ab23a719efb98`
  - schema: `root-prior-guided-search-comparison-v1`
- T048 assist_0 runs1000 comparison:
  `artifacts/t048-root-prior-guided-scale-up-pr/assist0-runs1000-full21-budget20-root-prior-comparison.jsonl`
  - sha256:
    `5807c4255c97a5018e189198180435e077b4d2698b66f6227e9580cb845cb398`
  - schema: `root-prior-guided-search-comparison-v1`
- T052 root-prior guided comparison:
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-root-prior-guided-comparison.jsonl`
  - sha256:
    `0cc496e6bddff0e5cecaee5e804d9ff4c89b2498093cb59d3feffbd245bb4a64`
  - schema: `root-prior-guided-search-comparison-v1`
- T052 result summary:
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-result-summary.json`
  - sha256:
    `1207ae0e93fa6f857add7dbaa553c3d92c86391772e842ce1e6bd08b55d97fe5`
- T053 failure-analysis report:
  `artifacts/t053-t052-root-prior-allocation-failure-analysis-pr/t053-root-prior-allocation-failure-analysis.json`
  - sha256:
    `73a1d153adce9782cafaf1caddb3fa0ddad2fafe33e653d88808875397832a73`
  - schema: `t053-root-prior-allocation-failure-analysis-v1`

Required guardrail-closure context inputs:

- T055 current T046-compatible guardrailed comparison:
  `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/current-t046-full8-budget20-guardrailed-comparison.jsonl`
  - sha256:
    `1580968ffd592433d838c3dde780148e43a33c145079f8a332dfcb1a2a9b0246`
- T055 assist_0 runs1000 guardrailed comparison:
  `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/assist0-runs1000-full21-budget20-guardrailed-comparison.jsonl`
  - sha256:
    `7a96015ad103cb6c06d092fd2bf03d7b194cef12d3053808bc444b649ae994da`
- T055 scale-validation report:
  `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/t055-guardrailed-root-prior-scale-validation-report.json`
  - sha256:
    `0e365f76fcde88d81917b587ae162843488527dd7b422a43998ab24a069cae04`
  - schema: `t055-guardrailed-root-prior-scale-validation-report-v1`

The primary output is a versioned
`t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1` JSON
report plus a concise formatted summary. Generated reports should remain under
an ignored stable path such as:

```text
artifacts/t057-existing-root-prior-allocation-telemetry-diagnostic-pr/
```

The PR must report generated report path, schema id, byte count, SHA-256 hash,
input artifact identities, command, unavailable diagnostics, and selected next
path.

## Scope

- Add an offline diagnostic workflow that consumes the required retained
  artifacts and runs no simulator.
- Verify all required input hashes, schemas, information regimes, cohort
  identities, task ids, required arms, and T056 recommendation before producing
  success output.
- Analyze the existing `root_prior_guided_oracle_search_v1` arm separately
  from baseline Oracle search, post-search `model_guided_oracle_search_v2`,
  and the abandoned guardrailed arm.
- Preserve cohort and distribution labels for:
  - T048 current T046-compatible 8-record cohort;
  - T048 assist_0 runs1000 21-record cohort;
  - T052 Boss-only subset;
  - T052 Act-2+ subset;
  - T053 disagreement records.
- Report per-record outcome deltas where matched records are available,
  including battle win/loss, terminal absolute HP, structured resource status,
  decision count, simulator step count, restore/truncation/controller status,
  and source identity.
- Summarize root-prior allocation telemetry for the existing root-prior arm:
  provided-prior counts, positive-prior counts, missing-prior counts, malformed
  allocation metadata, root-mapping failures, unsearched legal-action counts,
  selected target/action fields where available, root visit distribution, and
  model/checkpoint provenance.
- Explicitly evaluate selected-action identity availability and exact
  step-level comparison feasibility across required arms. If the retained
  artifacts cannot support exact comparison, report the missing fields and
  affected cohorts/records.
- Classify existing root-prior evidence into a bounded taxonomy such as:
  beneficial allocation signal, harmful allocation signal, no outcome change,
  terminal-HP-only change, distribution-specific conflict, and telemetry
  insufficient to assign cause.
- Recommend exactly one next task from this allowed set:
  - root-prior selected-action telemetry instrumentation or replay diagnostic;
  - existing-root-prior complete-run reachability probe;
  - another fixed-cohort diagnostic;
  - assisted/de-assisted checkpoint, teacher, or distribution-repair
    diagnostic;
  - source-generation, reachability, or non-combat-driver branch;
  - publish a blocked path requiring maintainer decision.

## Out Of Scope

- New simulator execution, restored-battle comparison, source collection,
  teacher collection, trainer-input generation, checkpoint training, or
  calibration runs.
- Any change to `root_prior_guided_oracle_search_v1`,
  `guardrailed_root_prior_guided_oracle_search_v1`, model-guided search, or
  non-combat behavior.
- Guardrail tuning, guardrail complete-run reachability, or reviving the
  T054/T055 guardrail path.
- Controller promotion, default-controller replacement, live-game validation,
  broad A20 teacher/checkpoint refresh, non-combat ranker implementation, or
  normal-information belief search.
- Treating fixed-cohort restored-battle evidence as natural A20 performance.

## Design Constraints

- All compared search evidence remains `full_simulator_state_oracle_like`.
- Missing telemetry must be explicit. Do not infer hidden state, missing
  selected actions, hidden future information, unrecorded native root rows, or
  causal allocation effects absent from retained artifacts.
- Keep outcome, terminal absolute current HP, and structured resources
  separate. Do not scalarize them into a fixed reward.
- Keep guardrailed root-prior evidence as abandoned-branch context only; it
  must not become the selected next implementation branch.
- CLI modules must remain limited to parsing and routing. Put reusable
  diagnostic logic below the command layer.

## Deliverables

- A versioned
  `t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1` report
  schema, writer, validator or reader, and formatted summary.
- An offline command or command workflow that consumes explicit artifact paths
  and writes the T057 report.
- Focused tests for input hash checking, required schema validation, cohort
  and arm validation, evidence-family separation, existing-root-prior-only
  allocation telemetry summaries, selected-action availability reporting,
  taxonomy assignment, exactly-one recommendation, and no-promotion wording.
- A PR report with consumed artifact identities, generated report identity,
  schema versions, telemetry availability, taxonomy counts, selected next
  path, rejected alternatives, verification results, known limitations, and
  documentation impact.

## Acceptance Criteria

- The T057 report verifies all required input hashes and schemas before
  reporting success.
- The report states that T056 selected
  `existing-root-prior allocation/telemetry diagnostic` and that the guardrail
  path remains closed.
- Existing root-prior allocation telemetry is reported separately for T048
  positive fixed-cohort evidence and T052/T053 later-act/Boss diagnostic
  evidence.
- Selected-action identity availability and exact step-level comparison
  feasibility are explicitly reported, with missing-field reasons where
  unavailable.
- The failure/diagnostic taxonomy is populated with counts or explicit
  unavailable reasons.
- The recommendation section names exactly one next task from the allowed set
  in Scope and explains why the telemetry evidence supports it.
- The report does not claim live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, final-agent status,
  or controller promotion.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T057 tests,
task-doc checks, and `git diff --check`.

T057 should not require WSL simulator execution. If the PR regenerates or
extends any prerequisite artifact, it must report the exact command, worker and
shard counts, record ranges, wall-clock cost, output path, SHA-256 hash, and
why regeneration was necessary. Any regenerated simulator stage must run
through WSL and follow the repository sharding/worker rule.

## Legacy Reference

Consult T047/T048 for root-prior guided comparison and allocation telemetry,
T052/T053 for later-act/Boss failure evidence and unavailable selected-action
diagnostics, T055 for the abandoned guardrail context, and T056 for the
path-selection evidence ledger. Do not reuse old smoke outputs or local
worktree artifacts without explicit current-schema provenance.

## PR Report

The PR must report task ID, consumed artifact identities, generated diagnostic
artifact identity, schema versions, cohort labels, controller arm labels,
selected-action availability, allocation telemetry summaries, taxonomy counts,
selected next path, rejected alternatives, unavailable diagnostics,
verification commands and results, known limitations, and documentation
impact.

## Historical Executor Note

T057 remains DONE and its scientific record is unchanged. Its task-specific
executor was retired by T072; executable historical source is available at
`09f58a7352f8dd860c2ed1d7f2b59beacb61d648`.
