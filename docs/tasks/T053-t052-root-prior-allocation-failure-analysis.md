# T053: T052 Root-Prior Allocation Failure Analysis

## Objective

Analyze why native root-prior guided search did not improve the T052
Boss/later-act fixed diagnostic cohort, using only the retained T052 artifacts
and explicit current-schema provenance.

This task is an offline diagnostic. It must explain the root-prior allocation
and matched-outcome signals in T052 before any root-prior repair task,
assisted training repair, broad teacher/checkpoint refresh, non-combat ranker
branch, or controller promotion. It remains `full_simulator_state_oracle_like`
evidence only.

## Current Main Baseline

T052 is complete. Its accepted retained artifact root is:

```text
artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/
```

Accepted T052 artifact identities:

- fixed cohort `t052-fixed-cohort.jsonl`:
  `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`;
- cohort summary `t052-cohort-summary.json`:
  `d778fdfe77d49ae5ad93d7d74a15078a901e4925b1056f2dcc35ba1bd35951d0`;
- root-prior guided comparison `t052-root-prior-guided-comparison.jsonl`:
  `0cc496e6bddff0e5cecaee5e804d9ff4c89b2498093cb59d3feffbd245bb4a64`;
- result summary `t052-result-summary.json`:
  `1207ae0e93fa6f857add7dbaa553c3d92c86391772e842ce1e6bd08b55d97fe5`;
- retention manifest `t052-retention-manifest.json`:
  `6830027aa23db10fd4ce3be17dbaf453e04ebbf9326622d23c3c8ff2b56f130e`.

The T052 cohort has 93 natural T051 starts: 88 Act-1 Boss starts and 5
Act-2+ starts. Overall results were baseline Oracle 4W/89L, post-search
model-guided 4W/89L, and root-prior guided 3W/90L. Boss-only results tied at
1W/87L for all three arms. Act-2+ results were baseline 3W/2L, post-search
3W/2L, and root-prior guided 2W/3L. Restore failures, truncations, controller
errors, and malformed root-prior allocation metadata were all zero in the
accepted T052 result summary.

## Dependencies

- T052 accepted retained cohort, comparison, result summary, and manifest.
- T047/T048 root-prior guided comparison schema and allocation telemetry.
- T051 source-arm provenance embedded in the T052 cohort.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts from the accepted T052
retained root. Do not use disposable review-worktree files or regenerated
outputs unless the PR reports them as new artifacts with commands and hashes.

Required inputs:

- T052 retention manifest with the accepted sha256 above;
- T052 fixed cohort with the accepted sha256 above;
- T052 root-prior guided comparison with the accepted sha256 above;
- T052 result summary with the accepted sha256 above.

The primary output is a versioned
`t053-root-prior-allocation-failure-analysis-v1` JSON report plus a concise
formatted summary. Generated reports should remain under an ignored stable path
such as:

```text
artifacts/t053-t052-root-prior-allocation-failure-analysis-pr/
```

The PR must report the generated report path, schema id, byte count, sha256,
input artifact identities, command, and any unavailable diagnostics.

## Scope

- Add an offline analysis workflow that consumes the T052 comparison and
  cohort artifacts without running the simulator.
- Identify matched source starts where the root-prior guided outcome differs
  from baseline Oracle search or post-search model-guided search, including the
  Act-2+ regression records and any Boss-only disagreements.
- Preserve per-record source identity: cohort index, source checkpoint id,
  T051 source arm role and label, source run id, battle index, act, room type,
  encounter id, public-context status, structured-outcome status, and
  information regime.
- Report per-arm battle outcome, terminal absolute current HP, structured
  resource status, decision count, simulator step count, wall-clock cost,
  restore status, truncation status, and controller problems for every
  disagreement record.
- Analyze root-prior guided decision telemetry where available: selected action
  identity, selected index, target, prior summary, allocation metadata, root
  visit distribution, positive-prior and missing-prior counts, malformed
  metadata, root-mapping failures, and unsearched legal-action counts.
- Compare root-prior guided selected actions against baseline and post-search
  selected actions where the T052 report exposes compatible per-decision action
  identities. If exact step-level matching is unavailable, mark that diagnostic
  unavailable with the missing field or schema reason.
- Summarize Boss-only and Act-2+ subsets separately. Do not collapse the
  five-record Act-2+ signal into a single overall average without the subset
  counts.
- Produce a failure taxonomy for the T052 evidence, with counts or explicit
  unavailable reasons for at least:
  - harmful root-prior allocation;
  - no-op or ineffective root-prior allocation;
  - weak or miscalibrated checkpoint prior;
  - native root outcome tie broken differently;
  - telemetry/schema insufficient to assign cause.
- Recommend exactly one next task, such as a root-prior prior-calibration
  repair, a guardrailed allocation experiment, an additional diagnostic over
  retained T052 starts, or a different blocked path. The recommendation must
  explain why T052/T053 evidence supports it.

## Out Of Scope

- New source collection, fixed-cohort evaluation, restored-battle comparison,
  teacher collection, trainer input generation, checkpoint training, or
  calibration runs.
- New controller behavior, root-prior allocation behavior, action-space
  behavior, or native `sts_lightspeed` API changes.
- Non-combat driver or ranker changes.
- Controller promotion, live-game validation, broad A20 training claims,
  natural A20 performance claims, normal-information claims, or final-agent
  claims.
- Replacing visible Boss information, constructing battle starts, or inferring
  hidden simulator state beyond fields already present in T052 artifacts.

## Design Constraints

- All analyzed search arms remain `full_simulator_state_oracle_like`.
- The analysis must preserve T052 cohort identity, comparison identity,
  checkpoint identity, source-arm provenance, and action-space configuration.
- Missing fields must be explicit. Do not guess action identities, target
  choices, native root rows, model priors, hidden state, or resource outcomes.
- Keep baseline Oracle search, post-search model-guided search, and root-prior
  guided search separate in every per-record and aggregate summary.
- Repeated source checkpoints, if any are discovered in inputs, must be
  reported from the T052 cohort metadata and not silently collapsed.
- CLI modules must remain limited to parsing and routing. Put reusable analysis
  logic below the command layer.

## Deliverables

- A versioned `t053-root-prior-allocation-failure-analysis-v1` report schema,
  writer, reader or validator, and formatted summary.
- An offline command or command workflow that consumes explicit T052 artifact
  paths and writes the T053 report.
- Focused tests with compact fixtures for input-hash checking, required-arm
  validation, matched-source validation, disagreement detection, unavailable
  telemetry reporting, subset aggregation, taxonomy assignment, and
  no-promotion wording.
- A PR report with consumed artifact paths and SHA-256 hashes, generated report
  path and hash, disagreement counts, Boss-only and Act-2+ findings, taxonomy
  outcome, exactly one recommended next task, verification results, known
  limitations, and documentation impact.

## Acceptance Criteria

- The command verifies the accepted T052 input hashes before analysis, or fails
  closed with a clear mismatch.
- Unsupported schemas, missing required arms, source/cohort mismatches, mixed
  information regimes, malformed allocation metadata, and missing required T052
  provenance fail closed or are reported as explicit unavailable diagnostics.
- The report lists all T052 disagreement records between root-prior guided
  search and either baseline Oracle search or post-search model-guided search.
- Act-2+ and Boss-only subsets are reported separately, including win/loss,
  terminal HP, decision counts, root-prior allocation summaries, and
  unavailable telemetry counts.
- The failure taxonomy is populated with counts, proportions, or exact
  unavailable reasons for every category named in Scope.
- The recommendation section names exactly one next task and does not claim
  implementation, controller promotion, live-game strength, natural A20
  performance, broad-training readiness, normal-information strength, or
  final-agent status.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T053 tests,
task-doc checks, and `git diff --check`.

T053 should not require WSL simulator execution. If the PR regenerates or
extends any T052 input artifact, it must report the exact command, worker and
shard counts, record ranges, wall-clock cost, output path, and SHA-256 hash,
and any restored-evaluation stage must follow the repository's WSL sharding
rule.

## Legacy Reference

Consult T045 for offline failure-analysis report patterns, T047/T048 for
root-prior guided comparison and allocation telemetry, T051 for source-arm
provenance, and T052 for the accepted retained fixed diagnostic cohort. Do not
reuse old smoke outputs or local worktree artifacts without explicit current
schema provenance.

## PR Report

The PR must report task ID, input artifact identities, generated report
identity, schema versions, T052 cohort identity, controller arm labels,
source/cohort match status, disagreement counts, Boss-only and Act-2+ subset
findings, allocation telemetry availability, failure taxonomy counts,
recommended next task, verification commands and results, known limitations,
and documentation impact.
