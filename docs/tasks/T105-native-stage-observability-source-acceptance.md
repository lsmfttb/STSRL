# T105: Native Particle/Search Stage Observability Source Acceptance

Artifact Eligibility Required: false

## Objective

Accept the independently reviewed and merged `sts_lightspeed` STSRL-007 stage-observability capability into STSRL as one exact, reproducible native source dependency before any T104 failure-population diagnostic re-entry consumes it.

T105 is an **integration/provenance acceptance task**. It is not a repair task, not a scientific replay of T104, and not a convergence experiment.

The native result to accept is:

- repository: `https://github.com/lsmfttb/sts_lightspeed.git`;
- active branch/ref: `stsrl/main` / `refs/heads/stsrl/main`;
- previous accepted STSRL manifest pin:
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`;
- native issue: `lsmfttb/sts_lightspeed#21` (`STSRL-007`);
- reviewed native PR: `lsmfttb/sts_lightspeed#22`;
- exact independently reviewed PR head:
  `38ab89618495dfc8b8e996fbcca44a93e5c18cfe`;
- independent exact-head semantic-review PASS comment:
  `5872517062`;
- merged native result:
  `5afae22def0c69657b0139bfa21306aebac831af`.

The sole task question is:

> can STSRL prove that exact merged native result is on the accepted `stsrl/main` lineage, pin it in the canonical source manifest, rebuild and verify it from a disposable checkout, and record the new non-secret monolithic bridge stage-observability contract without changing native behavior or consuming the T104 scientific failure population?

A successful T105 accepts only the observability capability required by a later bounded diagnostic re-entry.

## Publication Baseline

Publication base:

`main @ a2d23573043e1e89fb0b19857b343988b38845ba`

Current STSRL source manifest pin:

`97f59b620efe5ee1571f8da298c99d1e21c1149b`

Target pin:

`5afae22def0c69657b0139bfa21306aebac831af`

Active integration ref remains:

`refs/heads/stsrl/main`

At publication time Planner independently verified:

- `97f59b620efe5ee1571f8da298c99d1e21c1149b` is an ancestor of
  `5afae22def0c69657b0139bfa21306aebac831af`;
- exact reviewed native head
  `38ab89618495dfc8b8e996fbcca44a93e5c18cfe` is contained in the merged result lineage;
- native `refs/heads/stsrl/main` resolves exactly to
  `5afae22def0c69657b0139bfa21306aebac831af`.

Final acceptance must reproduce those facts independently.

## Dependencies

- T017: exact external source manifest and canonical source verifier.
- T020: single active `sts_lightspeed` integration-line governance.
- T099: accepted STSRL-006 particle/Search bridge capability and current native pin.
- T104: terminal `NATIVE_OBSERVABILITY_REQUIRED` and the six required monolithic diagnostic stages.
- Native issue `lsmfttb/sts_lightspeed#21`.
- Native PR `lsmfttb/sts_lightspeed#22`, independently accepted on exact head
  `38ab89618495dfc8b8e996fbcca44a93e5c18cfe` and merged as
  `5afae22def0c69657b0139bfa21306aebac831af`.

## Scope

### 1. Exact native source pin

Update `docs/sts_lightspeed_source_manifest.json` so:

- integration repository remains
  `https://github.com/lsmfttb/sts_lightspeed.git`;
- branch remains `stsrl/main`;
- ref remains `refs/heads/stsrl/main`;
- exact integration commit becomes
  `5afae22def0c69657b0139bfa21306aebac831af`.

The exact commit, not the moving ref, remains the reproducibility authority.

### 2. Source lineage proof

The implementation/final evidence must prove from the actual Git graph that:

- previous accepted pin
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`
  is an ancestor of
  `5afae22def0c69657b0139bfa21306aebac831af`;
- reviewed implementation head
  `38ab89618495dfc8b8e996fbcca44a93e5c18cfe`
  is contained in the merged result lineage;
- active `refs/heads/stsrl/main` resolves exactly to
  `5afae22def0c69657b0139bfa21306aebac831af`
  at acceptance time.

### 3. Canonical disposable-source verification

The canonical source verifier remains:

`scripts/verify_lightspeed_source.sh`

T105 must build/import the exact manifest-selected native source from a fresh/disposable worktree and verify the new capability from that module.

The verifier must not pass because of:

- stale native build directories;
- the STSRL-007 implementation worktree/branch;
- inherited caller `PYTHONPATH` pointing to another native module;
- copied binaries;
- local native source edits outside the pinned commit.

If STSRL verifier support must be extended, those changes must remain source/capability verification only. They must not recreate native hidden-state semantics in Python.

### 4. Additive native capability inventory

Add one explicit supported-native-capability record for STSRL-007 stage observability. Do not replace, reinterpret, or weaken the existing T099 `native_stsr006_particle_search_bridge` capability.

The new capability must require and describe at least:

- `StepSimulator.last_particle_search_stage_diagnostics`;
- schema `native-particle-search-stage-observability-v1`;
- top-level attempt status;
- `first_failed_stage`;
- stable coarse `failure_code`;
- `accepted_root_report_returned`;
- per-attempt particle rows and deterministic `particle_index` where one exists;
- all six T104-required monolithic stage names:
  - `hidden_future_sample_construction`;
  - `public_fidelity_validation`;
  - `root_occurrence_mapping`;
  - `search_setup`;
  - `search_execution`;
  - `sanitized_root_report`;
- stable stage-status vocabulary equivalent to
  `not_reached / entered / completed / failed`;
- `StepSimulator.stsr007_particle_search_stage_audit`;
- audit schema `native-stsr007-particle-search-stage-audit-v1`;
- audit evidence covering successful completion, early public/fidelity failure, occurrence-mapping failure, Search setup failure, Search execution failure, and sanitized-report failure.

The capability record must state that the stage telemetry is **control-flow observability**, not a game-mechanics root-cause claim.

### 5. Real-control-flow stage semantics

Verification must preserve the actual accepted native implementation order.

In the current STSRL-006 bridge, Search execution materializes the root edge surface used by occurrence mapping. Therefore the accepted implementation records:

```text
search_setup
-> search_execution
-> root_occurrence_mapping
-> sanitized_root_report
```

for that part of the native flow.

T105 must not reorder native execution merely to make stage names match the conceptual numbering in T104.

The verifier must confirm that stage status comes from structured native fields, never from parsing exception prose.

### 6. Information-safety contract

The accepted observability surface may expose only safe control-flow metadata already reviewed in STSRL-007.

STSRL verification must ensure the diagnostic surface does not expose:

- serialized or partial `BattleContext`;
- hidden draw order/identities beyond already accepted public/audit surfaces;
- native RNG state or unauthorized RNG outputs;
- Runic-Dome-hidden intent/private monster move identity;
- raw/replay native action bits;
- private Search tree state;
- hidden continuation trajectories;
- exception payload text used as scientific classification input.

The accepted stage surface may not become a controller/model feature by virtue of T105 acceptance.

### 7. Compatibility / no-repair boundary

T105 must verify that the native change is additive instrumentation only.

Required preserved behavior includes:

- existing T096/T098 public-information projection and hidden-future sampler semantics;
- existing STSRL-006 particle constructor;
- existing `sample_hidden_future_particles_search` success return semantics;
- existing unsupported-fidelity fail-closed behavior;
- existing occurrence-equivalence mapping semantics;
- existing `battle_search_v2` / Search-v2 behavior;
- existing sanitized root-report semantics;
- existing exception behavior on bridge failure, apart from the separately readable structured diagnostics.

T105 must not modify `sts_lightspeed`. If native behavior changes are found necessary, stop and return to the governed native issue/PR workflow.

## Artifact Eligibility Contract

None.

T105 consumes source identity, Git lineage, native capability metadata, and bounded verifier evidence only. It does not consume or produce a scientific corpus for a quality claim.

## Required Verification

At minimum, implementation must report and pass:

1. manifest parser/tests for exact pin
   `5afae22def0c69657b0139bfa21306aebac831af`;
2. exact Git lineage proof for old pin, reviewed PR head, merge result, and active ref;
3. canonical disposable-worktree verification through
   `scripts/verify_lightspeed_source.sh` against the exact pinned commit;
4. native API smoke against the verifier-built module;
5. existing T096 visibility/sampler regressions against that exact source;
6. existing STSRL-006 bridge regression/audit against that exact source;
7. `last_particle_search_stage_diagnostics()` availability and schema identity;
8. successful bridge witness with all six required stages consistently completed for accepted particle rows;
9. deterministic early/public-fidelity fail-closed stage witness;
10. deterministic occurrence-mapping fail-closed stage witness;
11. deterministic Search-setup, Search-execution, and sanitized-report stage-boundary audit evidence through the accepted test-only native audit surface;
12. proof that no exception-string parsing is required for stage classification;
13. proof that diagnostic output contains only the accepted safe fields and no hidden/native private payload;
14. existing Search-v2 geometry/state-utilization compatibility tests or equivalent checks sufficient to show instrumentation did not replace Search-v2 semantics;
15. ordinary repository quality gates required by `docs/tasks/README.md`.

This verification is bounded capability acceptance. Do **not** replay the 70/343 T104 populations in T105.

## Acceptance Criteria

T105 passes only if all of the following are true:

- STSRL manifest pins exactly
  `5afae22def0c69657b0139bfa21306aebac831af`;
- active integration ref remains `refs/heads/stsrl/main`;
- previous pin `97f59b6...` is proved ancestor of the merged result;
- reviewed native head `38ab896...` is proved included in the merged result;
- active native ref resolves exactly to the pinned result;
- canonical verifier builds/imports the exact pinned source from a disposable worktree;
- all pre-existing T096/T098/T099 capability checks needed by the bridge remain passing;
- the new stage-observability API/audit are required by the manifest/verifier;
- all six stages have stable structured status evidence;
- failed-stage evidence is obtained structurally rather than from exception prose;
- later untouched stages remain not reached rather than inferred;
- the real Search-before-root-mapping control-flow order is preserved rather than rewritten;
- the stage surface leaks no hidden Battle/RNG/Search-tree information;
- production bridge success/failure semantics remain unchanged apart from additive safe diagnostics;
- no T104 population replay, native repair, convergence, training, controller promotion, T034 closure, Non-Combat work, or T063/T066 activation occurs.

The intended successful terminal is:

`NATIVE_PARTICLE_SEARCH_STAGE_OBSERVABILITY_ACCEPTED`

## Failure / Incomplete Conditions

Use `SOURCE_LINEAGE_INVALID` if the new native result cannot be proved to descend from the accepted integration line, the reviewed head is absent from the merged lineage, or the active ref does not resolve to the pinned result.

Use `NATIVE_CAPABILITY_VERIFICATION_FAILED` if lineage is valid but clean build/import, API schema, stage semantics, compatibility, or deterministic audit checks fail.

Use `INFORMATION_SAFETY_CONTRACT_INVALID` if the accepted surface exposes hidden/private native data or requires free-form exception text as scientific classification evidence.

Use `INCOMPLETE` if required source identity or verifier evidence cannot be produced.

No non-success terminal authorizes T104 diagnostic re-entry.

## Explicit Non-Claims

T105 does not establish:

- the root cause of any of the 70 T104 Part-A cases;
- the root cause or stage distribution of the 343 T104 Part-B cases;
- that any current failure is a native mechanics bug;
- that any current failure has been repaired;
- particle support sufficiency;
- particle-count convergence;
- action-value/ranking convergence;
- posterior correctness or IID sampling;
- exact `Q_public` or information-set-optimal Search;
- Search/controller/model improvement;
- complete-run improvement;
- T034 completion;
- Non-Combat improvement;
- T063/T066 authorization.

## Out Of Scope

Do not perform or authorize in T105:

- the 70-case Part-A replay;
- the 343-case Part-B replay;
- any mechanics/sampler/projection/mapping/Search/root-report repair;
- exception-text causal parsing;
- N>2 particle convergence;
- cross-particle aggregation/action selection;
- model/student training or target generation;
- controller promotion;
- complete-run evaluation;
- T034 closure;
- Non-Combat policy work;
- T063/T066 activation.

## Successor Meaning

Only a successful
`NATIVE_PARTICLE_SEARCH_STAGE_OBSERVABILITY_ACCEPTED`
terminal allows Planner to publish a bounded T104 diagnostic re-entry using the accepted structured native stage surface.

That successor should preserve the accepted T104 frozen population/ordering and use the new native stage fields to localize the currently opaque bridge failures. It must remain diagnosis-first: no failure repair and no convergence should be bundled into that re-entry.

A successful T105 does **not** itself authorize that replay; Planner must publish a separate task contract after T105 lands.

## Execution Freedom And Material Changes

Maintainer/Implementer own ordinary implementation details including:

- verifier/helper/test decomposition;
- additive manifest capability wording that preserves this contract;
- exact bounded deterministic witness fixtures;
- shell/Git command formatting;
- local/WSL build orchestration;
- report/evidence-log layout.

A material change requires Planner amendment and renewed Maintainer exact-spec approval if it changes:

- exact accepted native commit;
- active native branch/ref;
- required ancestry relationships;
- six-stage structured observability semantics;
- real-control-flow ordering requirement;
- information-safety boundary;
- successful terminal meaning;
- prohibition on T104 replay/repair/convergence;
- successor ordering.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, Maintainer must independently review the exact task PR head and post:

```text
SPEC APPROVED

task: T105
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not require repeated Planner approval unless a material contract change above occurs.

Final landing requires Maintainer final implementation/operational acceptance and Planner final architecture/provenance acceptance on the same exact final PR head.

T104 diagnostic replay, native repair, convergence, training, controller promotion, T034 closure, Non-Combat work, and T063/T066 remain unauthorized until a later task explicitly permits them.
