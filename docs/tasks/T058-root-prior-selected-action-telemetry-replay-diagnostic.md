# T058: Root-Prior Selected-Action Telemetry Replay Diagnostic

## Objective

Close the selected-action telemetry gap identified by T057 for the existing
`root_prior_guided_oracle_search_v1` line.

The task must make exact all-arm step-level selected-action comparison
auditable for the retained T048 and T052 restored-battle evidence, or fail
closed with a precise native/replay blocker. It must not tune allocation,
change controller behavior, publish reachability evidence, or promote any
controller.

## Current Main Baseline

T057 is complete. It produced the stable
`t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1` artifact:

```text
artifacts/t057-existing-root-prior-allocation-telemetry-diagnostic-pr/t057-existing-root-prior-allocation-telemetry-diagnostic-report.json
sha256: 52c6742e9a578381e38cd66babe86363c97fc46e7fee374770427de17edf3c88
byte count: 3739962
schema: t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1
```

T057 verified the retained T048/T052/T053/T055 artifacts, summarized 122
existing-root-prior retained records and 2087 existing-root-prior decisions,
and kept the evidence inside the `full_simulator_state_oracle_like` restored
battle boundary. It found:

- selected-action exact comparison feasible for all records: `false`;
- selected-action availability: 0 available records and 122 unavailable
  records;
- taxonomy counts: 4 beneficial allocation signals, 2 harmful allocation
  signals, 101 no-outcome-change records, 15 terminal-HP-only changes, 1
  distribution-specific conflict, and 122 telemetry-insufficient records;
- exactly one next path:
  `root-prior selected-action telemetry instrumentation or replay diagnostic`.

The missing selected-action identities block causal interpretation of the T048
positive fixed-cohort signal versus the T052 Boss/later-act regression.

## Dependencies

T057, T052, T048, T046, and T043.

## Inputs And Artifacts

Required diagnostic input:

- `artifacts/t057-existing-root-prior-allocation-telemetry-diagnostic-pr/t057-existing-root-prior-allocation-telemetry-diagnostic-report.json`
  - sha256:
    `52c6742e9a578381e38cd66babe86363c97fc46e7fee374770427de17edf3c88`
  - schema: `t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1`

Required replay/cohort inputs:

- T048 current T046-compatible fixed cohort:
  `artifacts/t047-root-prior-guided-smoke-pr45/current-t046-source/t047-current-t046-a20-seed1-3-fixed-cohort.jsonl`
  - sha256:
    `f336492a7f3b4d9c74b60a636fea54905e6e685025c9e34f174bcfa076b132c3`
  - record range used by T057/T048: `0:8`
- T048 assist_0 runs1000 fixed cohort:
  `artifacts/t044-de-assisted-comparison-pr/runs1000-fixed-cohorts/assist_0-runs1000-fixed-cohort.jsonl`
  - sha256:
    `4ee0eb125ac37e870f0f2c950290b131f4693185c60b6c71cd46b5265a4d0037`
  - record range used by T057/T048: `0:21`
- T052 Boss/later-act fixed cohort:
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl`
  - sha256:
    `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`
  - record range used by T057/T052: `0:93`

Required checkpoint inputs:

- T043 assist_0 smoke checkpoint, used by the T048 current and T052
  comparisons:
  `artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt`
  - sha256:
    `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`
- T043 runs1000 assist_0 checkpoint, used by the T048 assist_0 comparison:
  `artifacts/t044-de-assisted-comparison-pr/t043-main-runs1000-assist_0-s4/t043-main-runs1000-assist_0-s4-checkpoint.pt`
  - sha256:
    `ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3`

Generated reports and large replay/comparison artifacts must remain under an
ignored stable path such as:

```text
artifacts/t058-root-prior-selected-action-telemetry-replay-pr/
```

The primary output is a versioned
`t058-root-prior-selected-action-telemetry-diagnostic-report-v1` JSON report
plus a concise formatted summary. If the task writes GB-scale replay or
comparison JSONL artifacts, it must also write a lightweight retention
manifest with schema ids, paths, SHA-256 hashes, byte counts, generation
commands, worker/shard counts, record ranges, wall-clock cost, compatibility
requirements, retention reason, downstream consumers, and deletion conditions.

## Scope

- Add or repair selected-action identity telemetry for current Oracle-like
  search decisions so baseline Oracle search, post-search
  `model_guided_oracle_search_v2`, and existing
  `root_prior_guided_oracle_search_v1` records expose comparable selected
  action identities.
- Preserve duplicate legal action disambiguation. A raw legal-action index is
  not enough; comparison must use the current occurrence-safe public action
  identity or an explicitly equivalent identity payload.
- Support either an instrumented restored-battle replay/comparison run or an
  offline replay extractor, but the produced report must verify exact all-arm
  step-level selected-action comparison against the retained T048 and T052
  record sets.
- Reproduce the three existing-root-prior retained evidence families from T057:
  T048 current T046-compatible, T048 assist_0 runs1000, and T052 Boss/later-act
  diagnostic. T052 subset reporting must preserve Boss-only, Act-2+, and T053
  disagreement-record group summaries.
- Report, per matched record and per decision where available, selected action
  identity, action label/kind/parameters, decision index, arm label, root
  allocation summary for the existing root-prior arm, first divergence versus
  baseline and post-search, terminal win/loss, terminal absolute current HP,
  structured resource status, restore/truncation/controller status, and source
  identity.
- Verify T057 input identity and compare the new selected-action availability
  result against T057's 0/122 unavailable baseline.
- Recommend exactly one next path after this diagnostic, choosing only from:
  existing-root-prior complete-run reachability probe; another fixed-cohort
  diagnostic; root-prior allocation repair experiment; assisted/de-assisted
  checkpoint, teacher, or distribution-repair diagnostic; source-generation,
  reachability, or non-combat-driver branch; publish a blocked path requiring
  maintainer decision.

## Out Of Scope

- Changing `root_prior_guided_oracle_search_v1`,
  `model_guided_oracle_search_v2`, baseline Oracle search action selection, or
  non-combat behavior.
- Tuning native root-prior allocation, reviving the T054/T055 guardrail, adding
  a new controller variant, or changing default controller routing.
- Complete-run source collection, reachability claims, teacher collection,
  trainer-input generation, checkpoint training, calibration, broad A20
  refresh, live-game validation, controller promotion, or normal-information
  belief search.
- Treating restored fixed-cohort replay evidence as natural A20 performance.

## Design Constraints

- All compared search evidence remains `full_simulator_state_oracle_like`.
- Missing selected-action telemetry must remain explicit. Do not infer hidden
  state, hidden draw order, hidden future information, duplicate action
  identity, or unrecorded native tree content.
- Keep battle outcome, terminal absolute current HP, and structured resources
  separate. Do not scalarize them into a fixed reward.
- Writers emit only current artifact schemas. Readers may accept legacy
  artifacts only through explicit migration or explicit missingness reporting.
- CLI modules stay limited to parsing and routing. Put reusable telemetry,
  replay, comparison, and report logic below the command layer.
- Real `sts_lightspeed` replay/comparison gates run through WSL with the
  torch-capable Python/runtime pairing used by the checkpoint-guided tasks.
  Do not mix the torch interpreter with a native extension compiled for another
  CPython ABI.

## Deliverables

- Versioned selected-action identity telemetry for search decisions, with
  tests covering duplicate legal actions and missing identity fail-closed
  behavior.
- A T058 report schema, writer, reader/validator, and formatted summary.
- An offline or WSL-backed command workflow that consumes explicit artifact
  paths and writes the T058 report.
- If replay/comparison artifacts are generated, deterministic sharded run
  scripts or documented commands plus a retention manifest.
- Focused tests for T057 input hash/schema validation, selected-action
  identity extraction, exact all-arm step-level comparison feasibility,
  evidence-family separation, T052 subset preservation, no-promotion wording,
  exactly-one recommendation, and legacy missing-telemetry handling.

## Acceptance Criteria

- The T058 report verifies the required T057 report, cohort artifacts, and
  checkpoint hashes before reporting success.
- Selected-action identity comparison uses occurrence-safe action identities,
  not raw indices alone.
- The report states whether exact all-arm step-level selected-action comparison
  is feasible for every retained T048/T052 record. If any record remains
  unavailable, the missing field, arm, cohort, and record index are explicit,
  and the selected recommendation must be a blocked path or narrower diagnostic
  rather than reachability or promotion.
- For successful retained records, the report includes first selected-action
  divergence summaries between existing root-prior, baseline, and post-search
  arms, while keeping outcome, HP, resources, and root allocation telemetry
  separate.
- The report preserves T048 current, T048 assist_0, T052 Boss-only, T052
  Act-2+, and T053 disagreement-record summaries.
- The report does not claim live-game strength, natural A20 performance,
  broad-training readiness, normal-information strength, final-agent status,
  controller promotion, or root-prior complete-run reachability.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T058 tests,
task-doc checks, and `git diff --check`.

If T058 runs restored-battle replay/comparison through WSL, use the
torch-capable runtime and report stage-by-stage worker evidence. The default
required stages are:

- T048 current T046-compatible replay/comparison: record range `0:8`, 8 shards
  and 8 workers unless a lower count is documented by a resource/tooling
  reason.
- T048 assist_0 runs1000 replay/comparison: record range `0:21`, 16 shards and
  16 workers unless a lower count is documented by a resource/tooling reason.
- T052 Boss/later-act replay/comparison: record range `0:93`, 16 shards and
  16 workers unless a lower count is documented by a resource/tooling reason.

Each WSL stage must report the exact command, Python path, native build path,
cohort path, checkpoint path, worker count, shard count, record range,
wall-clock cost, output path, SHA-256 hash, byte count, and logs.

T058 should not run complete-run source collection, teacher collection,
training, calibration, or live-game gates.

## Legacy Reference

Consult T025 for search telemetry boundaries, T047/T048 for root-prior guided
comparison plumbing, T052/T053 for later-act/Boss disagreement evidence, and
T057 for the selected-action availability baseline. Do not reuse old smoke
outputs or local worktree artifacts without explicit current-schema
provenance.

## PR Report

The PR must report task ID, implementation summary, consumed artifact
identities, generated report identity, any generated replay/comparison artifact
identities and retention manifest, selected-action availability before and
after T058, first-divergence summaries, T052 subset summaries, worker/shard
evidence for any WSL stages, verification commands and results, known
limitations, rejected alternatives, selected next path, and documentation
impact.

## Historical Executor Note

T058 remains DONE and its scientific record is unchanged. Its task-specific
executor was retired by T072; executable historical source is available at
`09f58a7352f8dd860c2ed1d7f2b59beacb61d648`.
