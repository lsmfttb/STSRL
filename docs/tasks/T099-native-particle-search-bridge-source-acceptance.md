# T099: Native Particle-Search Bridge Source Acceptance

Artifact Eligibility Required: false

## Objective

Accept the merged `sts_lightspeed` native public-consistent particle-to-Search bridge into STSRL as one exact, reproducible native source dependency before any particle-count convergence experiment consumes it.

T099 is an **integration/provenance acceptance task**, not a scientific convergence experiment.

The accepted native bridge is:

- repository: `https://github.com/lsmfttb/sts_lightspeed.git`;
- active branch/ref: `stsrl/main` / `refs/heads/stsrl/main`;
- previous STSRL manifest pin:
  `d309170198e21e57041a84dcfdbc255cdda4052e`;
- native issue: `lsmfttb/sts_lightspeed#19`;
- reviewed PR: `lsmfttb/sts_lightspeed#20`;
- exact independently reviewed PR head:
  `84fc8fd6d7e5a2d14170ac46f791a2a3fe6efaba`;
- merged native result:
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`.

The sole task question is:

> can STSRL prove the exact merged native bridge is on the accepted `stsrl/main` lineage, pin that exact commit in the canonical source manifest, rebuild and verify it from a disposable checkout, and record the bridge capability and its mixed information-regime semantics without relying on local native residue or unrecorded source state?

A successful T099 accepts only the native capability required by a later bounded convergence task. It does not itself average particle values, choose actions across particles, or establish any convergence or controller result.

## Publication Baseline

Publication base:

`main @ 9de817f027560507290544e288a5e48bada9e286`

The current STSRL source manifest pins:

`d309170198e21e57041a84dcfdbc255cdda4052e`

on:

`refs/heads/stsrl/main`.

T099 must advance that exact pin to:

`97f59b620efe5ee1571f8da298c99d1e21c1149b`

without changing the active integration branch/ref.

At publication time Planner independently verified:

- `d309170198e21e57041a84dcfdbc255cdda4052e` is an ancestor of
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`;
- reviewed native head
  `84fc8fd6d7e5a2d14170ac46f791a2a3fe6efaba`
  is an ancestor of the merged result;
- native `refs/heads/stsrl/main` resolves exactly to
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`.

Final acceptance must reproduce those facts independently.

## Dependencies

- T017: exact external source manifest and canonical source verifier.
- T020: single active `sts_lightspeed` integration-line governance.
- T096: accepted public-consistent hidden-future sampler substrate.
- T097: accepted visibility-aware current-information native source.
- T098: accepted fidelity re-entry terminal
  `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`.
- Native issue `lsmfttb/sts_lightspeed#19`.
- Native PR `lsmfttb/sts_lightspeed#20`, accepted on exact head
  `84fc8fd6d7e5a2d14170ac46f791a2a3fe6efaba` and merged as
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`.

## Scope

### 1. Exact native source pin

Update `docs/sts_lightspeed_source_manifest.json` so:

- integration repository remains
  `https://github.com/lsmfttb/sts_lightspeed.git`;
- branch remains `stsrl/main`;
- ref remains `refs/heads/stsrl/main`;
- exact integration commit becomes
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`.

The exact commit, not the moving ref, remains the reproducibility authority.

### 2. Source lineage proof

The PR report must prove from the actual Git graph that:

- previous accepted pin
  `d309170198e21e57041a84dcfdbc255cdda4052e`
  is an ancestor of
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`;
- exact reviewed implementation head
  `84fc8fd6d7e5a2d14170ac46f791a2a3fe6efaba`
  is contained in the merged result lineage;
- active `refs/heads/stsrl/main` resolves exactly to
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`
  at acceptance time.

The exact commands and outputs must be retained or reported.

### 3. Canonical disposable-source verification

The canonical source verifier remains:

`scripts/verify_lightspeed_source.sh`

T099 must rebuild the exact manifest-selected native source in a fresh/disposable worktree and verify the bridge against the resulting module.

The verifier must not pass because of:

- stale `build-py` or `build-stsrl-source-py`;
- an implementation worktree or temporary native branch;
- inherited caller `PYTHONPATH` pointing at another native module;
- copied native binaries;
- local source edits not contained in the pinned commit.

If verifier support must be extended, the changes belong in STSRL and must remain source/capability verification only. Python must not recreate hidden Battle mechanics or sampled full native state.

### 4. Native bridge capability inventory

Add one explicit manifest capability for the accepted STSRL-006 bridge.

The capability must require and describe at least:

- `StepSimulator.sample_hidden_future_particles_search`;
- the bridge schema / native API identity;
- `StepSimulator.stsr006_particle_search_audit`;
- the native STSRL-006 audit schema;
- reuse of the accepted T096/T098 particle construction semantics;
- public projection equality for supported particles;
- ordered public legal-action equality;
- Search-v2 root rows mapped back to public action occurrences;
- explicit occurrence-equivalence mapping provenance for Search-v2's existing mechanically deduplicated duplicate-card actions;
- sanitized returned root rows with no replay-only native action bits;
- Search work counters;
- explicit fail-closed behavior for unsupported anchors and incomplete/ambiguous mappings.

Do not replace or weaken the existing T096 capability record. T099 adds a bridge capability on top of the accepted sampler/visibility substrate.

### 5. Occurrence-equivalence contract

The accepted native bridge preserves every public legal-action occurrence while unchanged Search-v2 may represent mechanically equivalent adjacent duplicate card occurrences by one root edge.

T099 verification must assert that the native bridge exposes an explicit mapping contract, including the equivalent of:

- public action ordinal / public identity;
- source Search edge identity/index;
- mapping mode distinguishing direct mapping from mechanically deduplicated duplicate-card occurrence;
- source public action identity;
- count of public occurrences sharing the source edge.

The verifier must confirm that ordinary duplicate-card states are accepted when the native bridge identifies a valid Search-v2 mechanical equivalence class.

It must also confirm that raw replay-only action bits are not exposed as the normal public action identity.

T099 does not reimplement the Search-v2 duplicate-card predicate in Python as a second mechanics/search specification. Native audit evidence may be treated as authoritative for the exact equivalence behavior; STSRL-side verification should validate the returned contract and representative invariant rather than independently reconstructing hidden/native behavior.

### 6. Mixed information-regime semantics

The accepted capability has deliberately mixed semantics:

```text
public information state
    -> native public-consistent hidden-future sampler
    -> ephemeral full native particle
    -> unchanged full-state Search-v2 continuation
    -> sanitized per-particle root rows
```

The capability record and verifier must preserve this distinction.

Required semantic labels/conclusions:

- outer particle distribution:
  native public-consistent hidden-future sampler;
- per-particle continuation:
  `full_simulator_state_oracle_like` Search-v2;
- cross-particle aggregation:
  not performed by this capability;
- returned per-particle value semantics:
  `full_state_continuation_strategy_fusion_proxy`.

The capability must explicitly reject these claims:

- exact `Q_public(I,a)`;
- executable no-SL continuation value;
- information-set-optimal Search;
- exact Bayesian/deterministic-seed posterior expectation;
- IID posterior sampling.

## Artifact Eligibility Contract

None. T099 consumes source lineage and native capability evidence, not a learned checkpoint or generated scientific dataset.

## Required Verification

At minimum, implementation must report and pass:

1. manifest parser/tests for exact native pin
   `97f59b620efe5ee1571f8da298c99d1e21c1149b`;
2. exact Git lineage proof for old pin, reviewed PR head, merge result, and active ref;
3. canonical disposable-worktree verification:

   ```bash
   STSRL_LIGHTSPEED_BUILD_JOBS=16 bash scripts/verify_lightspeed_source.sh \
     /path/to/sts_lightspeed
   ```

4. native API smoke against the verifier-built exact module;
5. existing T096 visibility/sampler regressions against that exact source;
6. native `stsr006_particle_search_audit()` with every required audit predicate true;
7. one bounded ordinary bridge smoke through
   `sample_hidden_future_particles_search`;
8. duplicate-card occurrence mapping evidence showing public occurrences survive Search-v2 dedup with explicit equivalence provenance;
9. returned bridge rows contain no replay-only native action bits;
10. Frozen Eye/direct Search compatibility remains passing;
11. known draw-knowledge constraint preservation remains passing;
12. unsupported-fidelity anchor rejection remains passing;
13. existing Search-v2 tree-geometry/state-utilization or equivalent compatibility smoke sufficient to show the bridge did not replace Search-v2 semantics;
14. focused manifest/source-verifier tests and ordinary repository quality gates required by `docs/tasks/README.md`.

This is bounded capability verification. Do not run 2/4/8/16/32 convergence or a formal scientific cohort.

## Acceptance Criteria

T099 passes only if all of the following are true:

- STSRL manifest pins exactly
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`;
- active integration ref remains `refs/heads/stsrl/main`;
- old pin `d309170...` is proved ancestor of the merged result;
- reviewed native head `84fc8fd...` is proved included in the merged result;
- active native ref resolves exactly to the pinned result;
- canonical verifier builds and imports the exact pinned source from a disposable worktree;
- existing T096/T098 public-information and sampler capability regressions remain passing;
- the new bridge API and audit are required by the manifest/verifier;
- bridge particles preserve exact public projection and ordered public legal-action parity;
- duplicate public card occurrences survive Search-v2's existing mechanical dedup through explicit occurrence-equivalence mapping rather than silent dropping or unsupported rejection;
- incomplete/ambiguous root mappings fail closed;
- unsupported-fidelity anchors fail closed before an accepted Search batch is returned;
- returned public/root mapping rows expose no replay-only native action bits;
- sampled full native particle state is never reconstructed or exported through STSRL Python;
- the bridge is recorded as unchanged full-state Search-v2 continuation over public-consistent particles, not as public-information-optimal Search;
- no convergence experiment, cross-particle aggregation/action selection, Search algorithm change, model training, controller promotion, T034 closure, Non-Combat work, or T066 work occurs.

The intended successful terminal is:

`NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`

## Failure / Incomplete Conditions

Use `SOURCE_LINEAGE_INVALID` if the new native result cannot be proved to descend from the accepted integration line, the reviewed head is absent from the merged lineage, or the active ref does not resolve to the pinned result.

Use `NATIVE_CAPABILITY_VERIFICATION_FAILED` if lineage is valid but clean build/import, bridge API, occurrence mapping, parity, compatibility, or fail-closed checks fail.

Use `INFORMATION_REGIME_CONTRACT_INVALID` if the accepted STSRL surface exposes private full particle state, silently treats the proxy as `Q_public`, or otherwise collapses the mixed information-regime distinction.

Use `INCOMPLETE` if required source identity or verifier evidence cannot be produced.

No non-success terminal authorizes convergence.

## Explicit Non-Claims

T099 does not establish:

- particle-count sufficiency;
- numerical stability at 2/4/8/16/32 particles;
- action-value/ranking convergence;
- exact hidden-state posterior correctness;
- IID sampling;
- information-set-optimal continuation;
- exact `Q_public`;
- Search improvement;
- Battle controller improvement;
- learned policy/value improvement;
- complete-run improvement;
- arbitrary-mid-Battle universal support;
- T034 completion;
- Non-Combat improvement;
- deployment readiness; or
- T066 authorization.

## Out Of Scope

Do not perform or authorize in T099:

- 2/4/8/16/32 particle convergence;
- cross-particle Search-value aggregation;
- cross-particle action selection;
- information-state / action-observation Search implementation;
- Search-v2 algorithm changes;
- learned prior/value callbacks;
- model/student training or target generation;
- controller promotion;
- complete-run evaluation;
- new native simulator behavior changes;
- PRNG seed inference/reverse engineering;
- T034 closure;
- Non-Combat policy work;
- T066.

If fresh native behavior changes are found necessary, stop and return to the governed `sts_lightspeed` workflow. Do not modify native behavior from the STSRL task branch.

## Successor Meaning

Only a successful
`NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`
terminal allows Planner to publish one bounded particle-count convergence task.

That successor should hold a bounded public-state cohort and native/Search configuration fixed and measure the outer particle-integration proxy at nested counts such as:

```text
2 -> 4 -> 8 -> 16 -> 32
```

The successor must explicitly retain the strategy-fusion limitation: stability of the full-state-continuation proxy does not prove that the proxy is an information-set-optimal deployable value.

Poor stability at tens of particles should be treated as an architecture/economics warning rather than an automatic authorization to scale to hundreds or thousands.

## Execution Freedom And Material Changes

Maintainer/Implementer own ordinary implementation details including:

- verifier helper/test decomposition;
- manifest capability wording that preserves this contract;
- shell/Git command formatting;
- exact bounded bridge smoke state;
- local/WSL build orchestration;
- report/evidence-log layout.

A material change requires Planner amendment and renewed Maintainer exact-spec approval if it changes:

- the exact accepted native commit;
- active native branch/ref;
- required ancestry relationships;
- occurrence-equivalence semantics;
- the mixed information-regime claim boundary;
- the successful terminal meaning;
- the prohibition on convergence/aggregation/Search/training work;
- successor ordering.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, Maintainer must independently review the exact task PR head and post:

```text
SPEC APPROVED

task: T099
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not require repeated Planner approval unless a material contract change above occurs.

Final landing requires Maintainer final implementation/operational acceptance and Planner final architecture/provenance acceptance on the same exact final PR head.

Particle convergence, cross-particle aggregation/action selection, Search changes, training, controller promotion, T034 closure, Non-Combat work, and T066 remain unauthorized until a later task explicitly permits them.
