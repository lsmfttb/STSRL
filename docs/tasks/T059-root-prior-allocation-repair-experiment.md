# T059: Root-Prior Allocation Repair Experiment

## Objective

Test one bounded, versioned root-prior allocation repair variant after T058 made
selected-action divergence auditable for the existing
`root_prior_guided_oracle_search_v1` line.

The task determines whether a single allocation-side repair can preserve the
positive T048 fixed-cohort signal while removing or reducing the harmful T052
Boss/later-act selected-action divergences. It must not revive the T054/T055
guardrail path, run complete-run reachability, train or calibrate checkpoints,
or promote a controller.

## Current Main Baseline

T058 is complete. It produced the stable main-retained
`t058-root-prior-selected-action-telemetry-diagnostic-report-v1` artifact:

```text
artifacts/t058-root-prior-selected-action-telemetry-replay-pr/t058-root-prior-selected-action-telemetry-diagnostic-report.json
sha256: ffadf375902321888f25b6883c474f0060e6aa0e82c2102fb3e3afd29ae78a04
byte count: 8672745
schema: t058-root-prior-selected-action-telemetry-diagnostic-report-v1
```

The main-retained T058 manifest is:

```text
artifacts/t058-root-prior-selected-action-telemetry-replay-pr/t058-retention-manifest.json
sha256: faf3dacc6c7d887aae3ab8f6878aa67ec1f47edabd071178e70b03f29584172f
byte count: 18891
schema: t058-retention-manifest-v1
```

T058 verified the retained T048/T052 cohorts and checkpoints, regenerated
current-schema selected-action comparison artifacts, and kept all compared arms
inside the `full_simulator_state_oracle_like` restored-battle boundary. It
found:

- selected-action identity availability: 122 available records and 0
  unavailable records;
- exact all-arm step-level selected-action comparison feasible for all retained
  records: `true`;
- exact full-battle path comparison available for 11 records, with 111 partial
  records;
- first selected-action divergence between existing root-prior and both
  baseline Oracle search and post-search model-guided search on all 122
  records;
- 2 harmful selected-action divergence records in the T058 recommendation
  evidence;
- exactly one next path: `root-prior allocation repair experiment`.

Retained T058 outcome context:

- T048 current T046-compatible: baseline 5W/3L, post-search 5W/3L, existing
  root-prior 6W/2L;
- T048 assist_0 runs1000: baseline 11W/10L, post-search 11W/10L, existing
  root-prior 13W/8L;
- T052 Act-2+ subset: baseline 3W/2L, post-search 3W/2L, existing root-prior
  2W/3L;
- T052 Boss-only subset: all three existing arms tied at 1W/87L;
- T053 disagreement-record subset: baseline 3W/1L, post-search 3W/1L,
  existing root-prior 2W/2L.

T058 also reports one remaining diagnostic limitation: selected-action
telemetry makes chosen-action divergence auditable, but it does not expose
paired within-decision native counterfactual search trees.

## Dependencies

T058, T052, T048, T046, and T043.

## Inputs And Artifacts

Required T058 diagnostic inputs:

- T058 diagnostic report:
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/t058-root-prior-selected-action-telemetry-diagnostic-report.json`
  - sha256:
    `ffadf375902321888f25b6883c474f0060e6aa0e82c2102fb3e3afd29ae78a04`
  - schema: `t058-root-prior-selected-action-telemetry-diagnostic-report-v1`
- T058 retention manifest:
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/t058-retention-manifest.json`
  - sha256:
    `faf3dacc6c7d887aae3ab8f6878aa67ec1f47edabd071178e70b03f29584172f`
  - schema: `t058-retention-manifest-v1`

Required T058 comparison artifacts for diagnostic baselines:

- T048 current T046-compatible selected-action comparison:
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/current-t046-full8-budget20-t058-comparison.jsonl`
  - sha256:
    `f6c316e50121a118fdddf6921b38cb05f81cbc3e3024cf543eab3f9dfb091255`
  - byte count: `30838782`
- T048 assist_0 runs1000 selected-action comparison:
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/assist0-runs1000-full21-budget20-t058-comparison.jsonl`
  - sha256:
    `abcf6ae352e690e4ef1131485ae71d06f1be987a2680cd15ba1bd0f9215b2965`
  - byte count: `101353894`
- T052 Boss/later-act selected-action comparison:
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/t052-boss-later-act-full93-budget20-sharded-t058-comparison.jsonl`
  - sha256:
    `c6c27c1e554eb6b5211d2d4591ee5b9a7998fc0b7968c02df459a0d009513bbe`
  - byte count: `832319371`

Required cohort and checkpoint inputs:

- T048 current T046-compatible fixed cohort:
  `artifacts/t047-root-prior-guided-smoke-pr45/current-t046-source/t047-current-t046-a20-seed1-3-fixed-cohort.jsonl`
  - sha256:
    `f336492a7f3b4d9c74b60a636fea54905e6e685025c9e34f174bcfa076b132c3`
  - record range: `0:8`
- T048 assist_0 runs1000 fixed cohort:
  `artifacts/t044-de-assisted-comparison-pr/runs1000-fixed-cohorts/assist_0-runs1000-fixed-cohort.jsonl`
  - sha256:
    `4ee0eb125ac37e870f0f2c950290b131f4693185c60b6c71cd46b5265a4d0037`
  - record range: `0:21`
- T052 Boss/later-act fixed cohort:
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl`
  - sha256:
    `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`
  - record range: `0:93`
- T043 assist_0 smoke checkpoint, used by the T048 current and T052
  comparisons:
  `artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt`
  - sha256:
    `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`
- T043 runs1000 assist_0 checkpoint, used by the T048 assist_0 comparison:
  `artifacts/t044-de-assisted-comparison-pr/t043-main-runs1000-assist_0-s4/t043-main-runs1000-assist_0-s4-checkpoint.pt`
  - sha256:
    `ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3`

Generated reports and large comparison artifacts must remain under an ignored
stable path such as:

```text
artifacts/t059-root-prior-allocation-repair-experiment-pr/
```

The primary output is a versioned
`t059-root-prior-allocation-repair-report-v1` JSON report plus a concise
formatted summary. Any retained comparison JSONL, shard output, logs, scripts,
or report inputs must be listed in a lightweight retention manifest with schema
ids, paths, SHA-256 hashes, byte counts, generation commands, worker/shard
counts, record ranges, wall-clock cost, compatibility requirements, retention
reason, downstream consumers, and deletion conditions.

## Scope

- Add exactly one versioned root-prior allocation/search repair variant. The
  existing `root_prior_guided_oracle_search_v1` and the abandoned guardrailed
  variant must remain explicitly constructible for diagnostics.
- State the repair hypothesis before the restored-battle evaluation. The repair
  may use T058 selected-action and allocation telemetry to choose one bounded
  allocation-side change, but it may not run a hyperparameter sweep over the
  retained evaluation outcomes.
- The repair may adjust only how public checkpoint priors feed native root
  allocation. Final action selection must still follow native search result
  semantics, not direct checkpoint top-action selection.
- Do not use hidden future information, unrevealed encounter information, T058
  outcome labels, T053 disagreement labels, cohort index, or post-hoc knowledge
  as online controller inputs.
- Run restored-battle fixed-cohort comparisons over all retained T048/T052
  records at equal native root budget. Required arms are:
  - baseline Oracle search;
  - post-search `model_guided_oracle_search_v2`;
  - existing `root_prior_guided_oracle_search_v1`;
  - the new T059 allocation repair variant.
- Preserve and report evidence families separately:
  - T048 current T046-compatible 8-record cohort;
  - T048 assist_0 runs1000 21-record cohort;
  - T052 full 93-record Boss/later-act cohort;
  - T052 Boss-only subset;
  - T052 Act-2+ subset;
  - T053 disagreement-record subset as identified by T058/T053 provenance.
- Report per-record selected-action identity, first divergence versus baseline
  and post-search, allocation telemetry, terminal win/loss, terminal absolute
  current HP, structured resources, restore/truncation/controller status,
  source identity, model/checkpoint provenance, native budget, worker/shard
  provenance, and unavailable diagnostics.
- Recommend exactly one next task after T059 from this allowed set: scale the
  repaired variant on additional fixed cohorts; run a narrower diagnostic;
  abandon the allocation-repair path; run a bounded complete-run reachability
  probe for the repaired variant; publish a blocked path requiring maintainer
  decision.

## Out Of Scope

- Reviving, retuning, or promoting the T054/T055 guardrail path.
- More than one new allocation repair variant or a post-hoc tuning sweep.
- Controller promotion, default-controller replacement, live-game validation,
  natural A20 performance claims, broad-training readiness, final-agent claims,
  or normal-information search claims.
- Complete-run source collection, reachability evidence, teacher collection,
  trainer-input generation, checkpoint training, calibration, broad A20
  teacher/checkpoint refresh, assisted/de-assisted distribution repair, or
  non-combat ranker work.
- Changing baseline Oracle search, `model_guided_oracle_search_v2`, retained
  T048/T052 cohort artifacts, checkpoint artifacts, or fixed-cohort selection.
- Implementing Slay the Spire mechanics locally.

## Design Constraints

- All compared search evidence remains `full_simulator_state_oracle_like`.
- Keep battle outcome, terminal absolute current HP, and structured battle-end
  resources separate. Do not scalarize them into a fixed reward.
- Preserve action-space configuration, duplicate legal-action disambiguation,
  selected-action identity, allocation telemetry, source identity, public
  context status, structured-outcome/resource status, information regime, and
  controller provenance.
- Writers emit only current artifact schemas. Readers may accept old artifacts
  only through explicit migration or explicit missingness reporting.
- Fail closed on SHA-256 mismatches, unsupported schemas, source or cohort
  identity mismatches, missing required arms, mixed information regimes,
  restore failures that invalidate comparison, controller errors, malformed
  allocation metadata, or missing selected-action identity.
- Real `sts_lightspeed` restored-battle comparison gates must run through WSL
  and follow the repository worker/shard rule. On the current 16-logical-core
  maintainer machine, use 16 workers by default for substantial WSL stages
  unless the PR reports a concrete lower-worker resource or tooling reason.
- Use the torch-capable WSL Python/runtime pairing for checkpoint-guided stages.
  Do not mix the torch interpreter with a native extension compiled for another
  CPython ABI.

## Deliverables

- A versioned T059 root-prior allocation repair controller/configuration with
  complete provenance and telemetry.
- A current-schema `t059-root-prior-allocation-repair-report-v1` schema,
  writer, validator or reader, and formatted summary.
- CLI or command workflow for running the T059 comparisons from explicit
  artifact paths and writing the report/manifest.
- Focused tests covering new-version provenance, old-version constructibility,
  guardrail non-revival, allocation telemetry, selected-action identity
  preservation, input hash/schema fail-closed behavior, evidence-family
  separation, T053 disagreement subset aggregation, no-promotion wording, and
  report round trip.
- A retained T059 artifact manifest and PR evidence with exact paths, hashes,
  worker/shard counts, commands, wall-clock costs, and known limitations.

## Acceptance Criteria

- The existing root-prior guided controller remains constructible and
  behavior-compatible for existing tests.
- The T059 repair variant has a distinct versioned controller name and complete
  provenance.
- The T059 workflow verifies all required T058, T048, T052, T046, and T043
  artifact hashes and schemas before reporting success.
- The report evaluates all 122 retained records across the T048 current, T048
  assist_0, and T052 Boss/later-act cohorts, or fails closed with explicit
  missing record, arm, cohort, and stage reasons.
- Required arms are kept separate in every per-record, per-subset, and aggregate
  summary.
- The report states whether the repair improved, tied, or regressed versus
  existing root-prior guided search, baseline Oracle search, and post-search
  model-guided search at equal configured native root budget.
- The report separately states whether the repair preserved the positive T048
  fixed-cohort signal and whether it repaired or worsened the T052 Act-2+ and
  T053 disagreement-record regressions.
- Selected-action divergence is auditable for every successful retained record,
  using occurrence-safe action identities rather than raw indices alone.
- Restore failures, truncations, controller errors, malformed allocation
  metadata, source/cohort mismatches, mixed information regimes, or missing
  selected-action identities are not silently averaged into success claims.
- The recommendation section names exactly one next task and does not claim
  controller promotion, live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, or final-agent status.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T059 tests,
task-doc checks, and `git diff --check`.

Run restored-battle T059 comparisons through WSL with reported stage-by-stage
worker evidence. The default required stages are:

- T048 current T046-compatible comparison: record range `0:8`, 8 shards and 8
  workers unless a lower count is documented by a resource/tooling reason.
- T048 assist_0 runs1000 comparison: record range `0:21`, 16 shards and 16
  workers unless a lower count is documented by a resource/tooling reason.
- T052 Boss/later-act comparison: record range `0:93`, 16 shards and 16 workers
  unless a lower count is documented by a resource/tooling reason.

Each WSL stage must report the exact command, Python path, native build path,
cohort path, checkpoint path, worker count, shard count, record range,
wall-clock cost, output path, SHA-256 hash, byte count, and logs. If an
orchestrating command cannot keep the 16-worker T052 stage making visible
progress, use explicit external shards and report the shard merge process.

T059 should not run complete-run source collection, teacher collection,
training, calibration, live-game gates, or non-combat gates.

## Legacy Reference

Consult T046 for native root-prior allocation metadata, T047/T048 for
root-prior comparison plumbing, T052/T053 for later-act/Boss failure evidence,
T054/T055/T056 for the abandoned guardrail branch, and T058 for selected-action
telemetry. Do not reuse old smoke outputs or local worktree artifacts without
explicit current-schema provenance.

## PR Report

The PR must report task ID, implemented repair version and parameters,
pre-evaluation repair hypothesis, consumed artifact identities, generated
artifact identities, exact commands, worker/shard counts, cohort ranges,
wall-clock costs, controller arm labels, source/cohort match status,
all-record results, evidence-family results, T053 disagreement-index results,
Boss-only and Act-2+ results, selected-action divergence summaries, allocation
telemetry availability, unavailable diagnostics, exactly one recommended next
task, verification commands and results, known limitations, rejected
alternatives, and documentation impact.
