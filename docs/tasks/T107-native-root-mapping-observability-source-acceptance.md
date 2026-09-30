# T107: Native Root-Occurrence Mapping Observability Source Acceptance

Artifact Eligibility Required: false

## Objective

Accept the independently reviewed and merged `sts_lightspeed` STSRL-008 root-occurrence mapping subreason observability capability into STSRL as one exact, reproducible native source dependency before any exact-323 mapping-subreason diagnostic re-entry consumes it.

T107 is an **integration/provenance acceptance task**. It is not a mapping repair task, not a replay of the T106 population, not a public-fidelity diagnosis, and not a convergence experiment.

The native result to accept is:

- repository: `https://github.com/lsmfttb/sts_lightspeed.git`;
- active branch/ref: `stsrl/main` / `refs/heads/stsrl/main`;
- previous accepted STSRL manifest pin:
  `5afae22def0c69657b0139bfa21306aebac831af`;
- native issue: `lsmfttb/sts_lightspeed#23` (`STSRL-008`);
- reviewed native PR: `lsmfttb/sts_lightspeed#24`;
- exact independently reviewed PR head:
  `264dcacaf9236cd133d8e9147186ad3698b42a3f`;
- independent exact-head semantic-review PASS comment:
  `5902756875`;
- merged native result:
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`.

The sole task question is:

> can STSRL prove that exact merged native result is on the accepted `stsrl/main` lineage, pin it in the canonical source manifest, rebuild and verify it from a disposable checkout, and record the new non-secret root-occurrence mapping subreason contract without changing native behavior or consuming the T106 failure population?

A successful T107 accepts only the observability capability required by a later bounded exact-323 diagnostic re-entry.

## Publication Baseline

Publication base:

`main @ d1456a7bd1f8182d3bb6b611a537dda51c4c9075`

Current STSRL source manifest pin:

`5afae22def0c69657b0139bfa21306aebac831af`

Target pin:

`1458522294d967e8985e1fd52cc15d7ebe7f2acd`

Active integration ref remains:

`refs/heads/stsrl/main`

At publication time Planner independently verified:

- `5afae22def0c69657b0139bfa21306aebac831af` is an ancestor of
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- exact reviewed native head
  `264dcacaf9236cd133d8e9147186ad3698b42a3f` is contained in the merged result lineage;
- comparing the reviewed native head to the merged result reports no file differences;
- native `refs/heads/stsrl/main` resolves exactly to
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`.

Final acceptance must reproduce those facts independently.

## Dependencies

- T017: exact external source manifest and canonical source verifier.
- T020: single active `sts_lightspeed` integration-line governance.
- T099: accepted STSRL-006 particle/Search bridge capability.
- T105: accepted STSRL-007 stage-observability capability and previous native pin.
- T106: exact 343-row failure-stage census establishing 323 root-occurrence-mapping-stage failures and 20 public-fidelity-validation-stage failures.
- Native issue `lsmfttb/sts_lightspeed#23`.
- Native PR `lsmfttb/sts_lightspeed#24`, independently accepted on exact head
  `264dcacaf9236cd133d8e9147186ad3698b42a3f` and merged as
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`.

## Scope

### 1. Exact native source pin

Update `docs/sts_lightspeed_source_manifest.json` so:

- integration repository remains
  `https://github.com/lsmfttb/sts_lightspeed.git`;
- branch remains `stsrl/main`;
- ref remains `refs/heads/stsrl/main`;
- exact integration commit becomes
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`.

The exact commit, not the moving ref, remains the reproducibility authority.

### 2. Source lineage proof

The implementation/final evidence must prove from the actual Git graph that:

- previous accepted pin
  `5afae22def0c69657b0139bfa21306aebac831af`
  is an ancestor of
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- reviewed implementation head
  `264dcacaf9236cd133d8e9147186ad3698b42a3f`
  is contained in the merged result lineage;
- the merged result introduces no file-level semantic delta beyond the reviewed implementation head;
- active `refs/heads/stsrl/main` resolves exactly to
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`
  at acceptance time.

### 3. Canonical disposable-source verification

The canonical source verifier remains:

`scripts/verify_lightspeed_source.sh`

T107 must build/import the exact manifest-selected native source from a fresh/disposable worktree and verify the new capability from that module.

The verifier must not pass because of:

- stale native build directories;
- the STSRL-008 implementation worktree/branch;
- inherited caller `PYTHONPATH` pointing to another native module;
- copied binaries;
- local native source edits outside the pinned commit.

If STSRL verifier support must be extended, those changes must remain source/capability verification only. They must not recreate native hidden-state or mapping semantics in Python.

### 4. Additive native capability inventory

Add one explicit supported-native-capability record for STSRL-008 root-occurrence mapping subreason observability. Do not replace, reinterpret, or weaken the existing T099 `native_stsr006_particle_search_bridge` or T105 `native_stsr007_particle_search_stage_observability` capabilities.

The new capability must require and describe at least:

- `StepSimulator.last_particle_search_stage_diagnostics`;
- per-particle additive field `root_occurrence_mapping_diagnostic`;
- diagnostic schema `native-root-occurrence-mapping-diagnostic-v1`;
- `status` semantics tied to the same bridge attempt;
- closed `mapping_subreason` vocabulary containing:
  - `no_public_legal_action_surface`;
  - `multiple_direct_search_root_matches`;
  - `missing_non_card_direct_search_root_match`;
  - `card_not_adjacent_mechanical_duplicate`;
  - `representative_search_root_match_zero`;
  - `representative_search_root_match_multiple`;
  - `uncovered_search_root_edge`;
  - `mapping_completed`;
- safe bounded structural fields sufficient to distinguish the accepted branches, including public occurrence/action-kind metadata, aggregate public/root-edge counts, mapping/coverage counts, and zero/one/multiple match categories where present;
- `StepSimulator.stsr008_root_occurrence_mapping_audit`;
- audit schema `native-stsr008-root-occurrence-mapping-audit-v1`;
- deterministic audit evidence for successful completion and all seven fail-closed mapping branches.

The capability record must state that this telemetry identifies a **mapping control-flow subreason**, not a game-mechanics root cause and not repair efficacy.

### 5. Direct production-branch semantics

Verification must establish that `mapping_subreason` is written directly by the native production mapping control flow, not derived from exception prose.

At minimum the accepted source must preserve the reviewed semantics:

- no-public-action code is written at the existing empty legal-action branch;
- multiple-direct code is written at the existing `directMatches.size() > 1` branch;
- missing-non-card code is written at the existing non-card/no-direct-match branch;
- duplicate representative-ineligibility code is written at the accepted adjacent mechanical-duplicate eligibility failure;
- representative zero/multiple codes are written at the split forms of the previously fail-closed `equivalentMatches.size() != 1` condition;
- uncovered-edge code is written at the existing edge-without-public-occurrence validation;
- `mapping_completed` is written only after all accepted mapping checks succeed.

STSRL verification must not classify mapping subreasons by parsing free-form native exceptions.

### 6. Information-safety contract

The accepted diagnostic surface may expose only the bounded non-secret structural metadata reviewed in STSRL-008.

STSRL verification must ensure it does not expose:

- raw/native action bits;
- raw or reconstructed `specialData` values;
- serialized or partial hidden `BattleContext`;
- hidden draw order or identities beyond already accepted public/audit surfaces;
- native RNG state or unauthorized RNG outputs;
- Runic-Dome-hidden intent/private monster move identity;
- private Search tree nodes/edges beyond safe aggregate counts;
- hidden continuation trajectories;
- arbitrary exception payload text used as scientific classification input.

The accepted mechanical-equivalence predicate may continue to use `specialData` internally exactly as before. T107 must not make that private field part of the STSRL diagnostic surface.

### 7. Test-injection isolation

The accepted native deterministic audit uses internal failure injection to exercise otherwise difficult branches. T107 must verify that production consumers cannot select that injection.

Required:

- production `StepSimulator.sample_hidden_future_particles_search` exposes no injection argument;
- ordinary production calls use the default `ParticleSearchFailureInjection::NONE` path;
- the internal injection enum/argument is not exposed through the production pybind bridge API;
- `StepSimulator.stsr008_root_occurrence_mapping_audit` may invoke fixed internal injections only inside its bounded deterministic audit fixture;
- no caller-supplied bridge request can opt into an injected failure mode.

### 8. Compatibility / no-repair boundary

T107 must verify that the native change is additive instrumentation only.

Required preserved behavior includes:

- existing T096/T098 public-information projection and hidden-future sampler semantics;
- existing STSRL-006 particle constructor and particle distribution;
- existing public-fidelity validation and ordered public legal-action construction;
- existing Search-v2 setup, execution, tree policy, backup, values, action enumeration, and work;
- Search-before-root-mapping execution order;
- existing direct action-bit matching semantics;
- existing mechanical duplicate predicate and representative walk;
- existing fail-closed mapping outcomes;
- existing sanitized root-report semantics;
- T105 stage order, failure code, and stage status semantics;
- RNG consumption for equivalent production bridge requests;
- existing `sample_hidden_future_particles_search` success and failure behavior apart from additive safe diagnostics.

T107 must not modify `sts_lightspeed`. If native behavior changes are found necessary, stop and return to the governed native issue/PR workflow.

## Artifact Eligibility Contract

None.

T107 consumes source identity, Git lineage, native capability metadata, and bounded verifier evidence only. It does not consume or produce a scientific corpus for a quality claim.

## Required Verification

At minimum, implementation must report and pass:

1. manifest parser/tests for exact pin
   `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
2. exact Git lineage proof for old pin, reviewed PR head, merge result, and active ref;
3. proof that reviewed head -> merged result has no file differences;
4. canonical disposable-worktree verification through
   `scripts/verify_lightspeed_source.sh` against the exact pinned commit;
5. native API smoke against the verifier-built module;
6. existing T096 visibility/sampler regressions against that exact source;
7. existing STSRL-006 bridge regression/audit against that exact source;
8. existing STSRL-007 stage-observability regression/audit against that exact source;
9. `last_particle_search_stage_diagnostics()` availability and accepted parent stage schema;
10. `root_occurrence_mapping_diagnostic` availability and schema identity;
11. successful mapping witness reporting `mapping_completed` while preserving the accepted semantic root report;
12. deterministic audit witnesses for all seven required failure subreasons;
13. proof each subreason is native structured data and no exception-string parsing is required;
14. proof that the diagnostic snapshot contains only the accepted safe structural fields;
15. proof that raw action bits, `specialData`, hidden Battle/Search/RNG/intent/trajectory data are not exposed by the new diagnostic;
16. proof that test injection is unavailable as a production bridge argument or caller-selectable API;
17. existing Search-v2 geometry/state-utilization compatibility tests or equivalent checks sufficient to show observability did not replace or alter Search-v2 semantics;
18. ordinary repository quality gates required by `docs/tasks/README.md`.

This verification is bounded capability acceptance. Do **not** replay the T106 323 mapping-stage identities or the 20 public-fidelity-stage identities in T107.

## Acceptance Criteria

T107 passes only if all of the following are true:

- STSRL manifest pins exactly
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- active integration ref remains `refs/heads/stsrl/main`;
- previous pin `5afae22...` is proved ancestor of the merged result;
- reviewed native head `264dcac...` is proved included in the merged result;
- merged result has no file-level semantic delta beyond reviewed head;
- active native ref resolves exactly to the pinned result;
- canonical verifier builds/imports the exact pinned source from a disposable worktree;
- all pre-existing T096/T098/T099/T105 capability checks needed by the bridge remain passing;
- the new mapping diagnostic API/audit is required by the manifest/verifier;
- all seven accepted failure subreasons plus successful `mapping_completed` are structurally verified;
- subreason evidence is obtained directly from structured native fields rather than exception prose;
- the diagnostic surface leaks no raw bits, `specialData`, hidden Battle/RNG/intent/Search-tree/trajectory information;
- internal test injection cannot be selected by production bridge callers;
- production sampler, projection, Search-v2, mapping, RNG, sanitized-report, stage, and pass/fail semantics remain unchanged apart from additive safe diagnostics;
- no T106 population replay, mapping repair, public-fidelity diagnosis, convergence, training, controller promotion, T034 closure, Non-Combat work, or T063/T066 activation occurs.

The intended successful terminal is:

`NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED`

## Failure / Incomplete Conditions

Use `SOURCE_LINEAGE_INVALID` if the new native result cannot be proved to descend from the accepted integration line, the reviewed head is absent from the merged lineage, the reviewed-head-to-merge equivalence check fails, or the active ref does not resolve to the pinned result.

Use `NATIVE_CAPABILITY_VERIFICATION_FAILED` if lineage is valid but clean build/import, API schema, mapping-subreason semantics, compatibility, deterministic audit, or production-injection isolation checks fail.

Use `INFORMATION_SAFETY_CONTRACT_INVALID` if the accepted surface exposes hidden/private native data, raw bits/non-public card fields, or requires free-form exception text as scientific classification evidence.

Use `INCOMPLETE` if required source identity or verifier evidence cannot be produced.

No non-success terminal authorizes the exact-323 diagnostic re-entry.

## Explicit Non-Claims

T107 does not establish:

- the mechanics root cause of any of the 323 T106 mapping-stage failures;
- the invariant-family or mechanics root cause of the 20 T106 public-fidelity-stage failures;
- that any mapping failure has been repaired;
- that a public-semantic Search-edge redesign is required or preferable;
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

Do not perform or authorize in T107:

- replay of the exact 323 T106 mapping-stage identities;
- diagnosis or replay of the separate 20 public-fidelity-stage identities;
- any mapping/equivalence/Search/sampler/projection/fidelity/root-report repair;
- replacement of the current adapter with a public-semantic Search-edge architecture;
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
`NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED`
terminal allows Planner to publish a bounded exact-323 mapping-subreason diagnostic re-entry using the accepted native structured mapping diagnostics.

That successor must preserve the exact T106 323 identities, ordering, replicate-0 seed derivation, N=2, unguided Search-v2@400, no-potions boundary unless a later Planner contract explicitly establishes a different scientific question. It must classify only from the accepted structured `mapping_subreason` surface and remain diagnosis-first: no mapping repair and no N>2 convergence bundled into that diagnostic.

The separate 20 public-fidelity-stage cases remain an independent diagnostic lane using the already accepted public/fidelity projection surface. T107 neither blocks nor executes that diagnosis, but it must not mix those 20 cases into the 323 mapping taxonomy.

A successful T107 does **not** itself authorize either diagnostic replay; Planner must publish a separate task contract.

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
- required ancestry/equivalence relationships;
- accepted mapping-subreason vocabulary or direct-production-branch semantics;
- information-safety boundary;
- production test-injection isolation;
- successful terminal meaning;
- prohibition on T106 replay/repair/convergence;
- successor ordering.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, Maintainer must independently review the exact task PR head and post:

```text
SPEC APPROVED

task: T107
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not require repeated Planner approval unless a material contract change above occurs.

Final landing requires Maintainer final implementation/operational acceptance and Planner final architecture/provenance acceptance on the same exact final PR head.

Exact-323 diagnostic replay, the separate 20-case fidelity diagnosis, native repair, convergence, training, controller promotion, T034 closure, Non-Combat work, and T063/T066 remain unauthorized until a later task explicitly permits them.
