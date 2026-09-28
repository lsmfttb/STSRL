# T106: Structured Particle/Search Failure-Stage Diagnostic Re-entry

Artifact Eligibility Required: true

## Objective

Use the T105-accepted non-secret native stage-observability surface to replay the exact 343 T104 Part-B opaque bridge-failure identities and establish an auditable control-flow failure-stage census under the unchanged N=2/Search-v2 boundary.

T106 is a **diagnostic re-entry**, not a repair task and not a convergence experiment.

T104 established that all 343 Part-B rows still lacked a concrete monolithic bridge repair boundary:

- 323 were `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS`;
- 20 were `STANDALONE_SAMPLER_FAILURE`;
- all 343 had `native_observability_required=true`;
- all six monolithic internal stages were `unknown`.

T105 then accepted `sts_lightspeed` STSRL-007 stage observability on the exact native pin:

`5afae22def0c69657b0139bfa21306aebac831af`

The sole T106 scientific question is:

> when those exact 343 accepted T104 Part-B identities are replayed once through the unchanged full particle/Search bridge with the same deterministic N=2 configuration, which first failed native control-flow stage is directly reported for each candidate, and what exact stage/failure-code distribution results?

T106 does not attempt to identify the underlying game-mechanics bug inside a failed stage. A structured stage is a repair boundary, not automatically a root cause.

## Publication Baseline

Planner publication base:

`main @ c86d1ce0e9f60811f90175a5f4793efd9e836858`

Accepted predecessor terminals:

- T104: `NATIVE_OBSERVABILITY_REQUIRED`;
- T105: `NATIVE_PARTICLE_SEARCH_STAGE_OBSERVABILITY_ACCEPTED`.

Accepted T104 scientific producer:

`90cbe6c5020f2fb360503e7731c9a892afc6447a`

Accepted T104 retained artifacts:

- candidate rows: `t104-bridge-localization-rows-v1`, SHA-256 `3232719325d790dcc84f7e91f907d12b56da37c7557edc8848a5f38fe530dd41`;
- aggregate report: `t104-bridge-localization-report-v1`, SHA-256 `d59e5c9c09dd780a522b018be045dc0656d1e0fe4f78f6406a204684a54ef0ff`;
- retention manifest: `t104-localization-retention-manifest-v1`, SHA-256 `e1d380177f3f68484809b6bac99f7d3477c3ad29e16229f08e70aa46d52da7ba`.

Current accepted native source identity:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 5afae22def0c69657b0139bfa21306aebac831af`

This native pin differs from T104 only through the independently reviewed and source-accepted STSRL-007 observability change. T106 nevertheless must empirically reproduce each selected candidate's full-bridge failure before interpreting its stage trace.

## Dependencies

- T081: fail-closed artifact eligibility and integrity rules.
- T098/T099: accepted public-information sampler and particle/Search bridge semantics.
- T101/T103: exact natural Battle-start source population, ordering, replicate-0 seed derivation, and N=2 support boundary.
- T104: accepted 343-row Part-B population, old standalone-sampler strata, and retained evidence.
- T105: exact native pin and accepted structured stage-observability contract.

## Artifact Eligibility Contract

Reuse mode: `scientific_quality_claim`.

Artifact eligibility claim boundary: T106 may claim only the bounded structured failure-stage distribution of the exact accepted T104 Part-B 343 identities under the frozen T101/T104 N=2/Search-v2 configuration and the T105-accepted observability-only native pin. T106 evidence is unavailable for repair efficacy, support improvement, N>2 convergence, controller quality, model training, or claims outside this frozen cohort.

Required inputs:

- accepted T104 candidate-localization rows, aggregate report, retention manifest, and execution record;
- exact T104 Part-B 343 selection identities in original T101/T104 order;
- accepted restore/source artifacts referenced by the T104 retention manifest and required to reproduce those identities;
- current canonical `sts_lightspeed` source manifest pinning `5afae22def0c69657b0139bfa21306aebac831af`;
- T105 source-acceptance contract and execution evidence establishing `native-particle-search-stage-observability-v1`;
- generated T106 per-candidate rows, aggregate report, execution record, and retention manifest.

Required predicates:

- exact T104 artifact kind/schema/path/SHA-256 and producer provenance match the accepted records above;
- selected population is exactly 343 unique T104 Part-B identities, preserving T101/T104 source ordinal and order;
- accepted T104 Part-B strata are exactly 323 `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` and 20 `STANDALONE_SAMPLER_FAILURE`;
- accepted A/B/C totals for the 343 rows are exactly 89/189/65;
- current native identity equals the T105-accepted pin exactly;
- each replay is bound to the accepted replicate-0 seed and frozen bridge/Search parameters;
- stage classification uses only the accepted structured trace and never exception prose;
- no generated T106 evidence is reused as repair or convergence evidence.

Unavailable: if any required artifact, hash, producer identity, selection identity, restore/source binding, seed, native identity, or qualification fact is missing, conflicting, malformed, unverifiable, or unavailable, fail closed to `INCOMPLETE`.

## Frozen Scientific Boundary

For every selected identity, preserve exactly:

- T101/T104 source identity and source ordinal;
- original T104 Part-B class as historical stratification only;
- replicate index `0` and accepted deterministic seed derivation;
- `particle_start=0`;
- `particle_count=2`;
- `search_simulations=400`;
- `include_potions=false`;
- unchanged unguided Search v2;
- current accepted native pin `5afae22def0c69657b0139bfa21306aebac831af`;
- no retry with altered seed, particle count, Search budget, potion setting, or other bridge semantics.

Each scientific replay must use a fresh restored adapter/clone so another diagnostic call cannot consume or mutate the state being classified.

The production bridge call is the scientific event. After it returns or throws, read `last_particle_search_stage_diagnostics()` immediately, before any later bridge call on that simulator can overwrite the snapshot.

## T104 Part-B Baseline Reproduction Gate

Every one of the exact 343 selected identities must be replayed through the full bridge.

Expected baseline:

- the full bridge does not return an accepted root report for any of the 343 identities;
- each invocation remains a fail-closed/exceptional bridge outcome as in T104.

If any selected candidate now returns an accepted root report under the frozen configuration, or otherwise no longer reproduces the accepted T104 full-bridge failure, terminate scientific interpretation as:

`T104_PART_B_BASELINE_NOT_REPRODUCED`

Retain the exact contradictory identities and structured traces, but do not fold them into the failure-stage census and do not reinterpret the change as an observability result.

The 70 T104 Part-A `PROJECTION_FAILURE_LOCALIZATION_OPAQUE` identities are **not** replayed by T106. Their accepted representation-boundary result remains unchanged and outside this task's claim boundary.

## Structured Native Trace Contract

For every failed bridge invocation, T106 must read and validate the T105-accepted schema:

`native-particle-search-stage-observability-v1`

Required top-level fields remain exactly the accepted safe surface:

- `attempt_status`;
- `first_failed_stage`;
- `failure_code`;
- `accepted_root_report_returned`;
- per-attempt particle rows with safe `particle_index` where available;
- the six stage statuses.

The six stages, in real native execution order, are:

1. `hidden_future_sample_construction`;
2. `public_fidelity_validation`;
3. `search_setup`;
4. `search_execution`;
5. `root_occurrence_mapping`;
6. `sanitized_root_report`.

Search execution intentionally precedes root occurrence mapping because Search materializes the root edge surface. T106 must not reorder or reinterpret this control flow.

Allowed stage statuses are the T105-accepted closed vocabulary:

`not_reached / entered / completed / failed`

T106 must use the repository's strict T105 trace validator or an equivalent contract-preserving wrapper. It must reject extra/private fields rather than silently retaining them.

## Candidate Failure-Stage Classification

Each reproduced Part-B failure receives exactly one mutually exclusive candidate class, derived only from the structured native trace:

1. `REQUEST_OR_PREFLIGHT_FAILURE`
   - `attempt_status=failed_closed`;
   - no particle-stage failure is established;
   - accepted T105 structured metadata identifies the request/preflight boundary.
2. `HIDDEN_FUTURE_SAMPLE_CONSTRUCTION_FAILURE`
3. `PUBLIC_FIDELITY_VALIDATION_FAILURE`
4. `SEARCH_SETUP_FAILURE`
5. `SEARCH_EXECUTION_FAILURE`
6. `ROOT_OCCURRENCE_MAPPING_FAILURE`
7. `SANITIZED_ROOT_REPORT_FAILURE`

For classes 2-7, the class is exactly the structured `first_failed_stage` translated to the corresponding stable T106 label. No exception message, exception substring, retained T103/T104 RuntimeError signature, historical standalone-sampler result, or inferred mechanics may override that field.

A `failure_code` is retained as a second, coarse structured dimension. It is not a root-cause label. Aggregate and cross-tab by code only within the accepted closed T105 vocabulary.

If a failed bridge invocation yields missing, malformed, unsafe, contradictory, or validator-rejected T105 telemetry, terminate as:

`NATIVE_OBSERVABILITY_CONTRACT_NOT_REPRODUCED`

Do not create an `UNKNOWN` stage by parsing the exception. The purpose of T105 was to remove that inference path.

## Historical T104 Stratification

Do not rerun standalone sampler probes in T106.

For each identity, carry forward its accepted T104 historical Part-B stratum:

- `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` (323 total; A/B/C = 84/174/65);
- `STANDALONE_SAMPLER_FAILURE` (20 total; A/B/C = 5/15/0).

These labels are covariates for cross-tabulation only. In particular:

- historical standalone sampler success does not prove the monolithic hidden-future construction stage succeeds in the T106 bridge replay;
- historical standalone sampler failure does not prove the monolithic bridge fails at hidden-future construction;
- any disagreement between historical standalone behavior and current structured monolithic stage is evidence about surface differences, not permission to invent a cause.

## Required Per-Candidate Evidence

Retain one row for every selected T104 Part-B identity with at least:

- exact T104 selection identity, source ordinal/digest, A/B/C stratum, and historical Part-B class;
- accepted T104 row/artifact provenance;
- exact current native identity;
- replicate-0 seed and frozen call parameters;
- bridge return/exception outcome;
- T105 trace schema id and top-level attempt status;
- top-level first failed stage;
- structured coarse failure code;
- accepted-root-report boolean;
- all available per-particle indices and complete six-stage status vectors;
- derived T106 mutually exclusive stage class;
- explicit indication that classification source is structured telemetry;
- bounded exception type/signature for audit only, never causal classification;
- wall-clock/resource evidence required by the execution framework.

Do not retain hidden Battle state, RNG state, hidden intent, replay-only native action bits, private Search tree state, hidden continuation trajectories, or free-form exception messages as scientific features.

## Aggregate Analysis

The final report must contain exact integer counts and fractions for:

- all seven T106 candidate classes overall;
- all seven classes by A/B/C stratum;
- all seven classes by the two historical T104 Part-B strata;
- stage class × structured failure-code cross-tab;
- first failing particle index where the accepted safe trace directly exposes one;
- complete stage-status transition signatures observed, using only the six safe statuses;
- exact count of replayed failures with valid telemetry;
- exact count of any baseline contradictions;
- exact count of any telemetry-contract violations.

All mutually exclusive stage-class counts must sum exactly to 343 for the successful terminal.

Do not report exception-message clusters as scientific causes. Historical exception signatures may be retained as audit grouping only and must be clearly separated from the structured stage census.

No p-value, confidence interval, causal generalization, or population claim outside the frozen 343-row cohort is required.

## Canary and Execution Safety

A bounded canary is allowed to validate plumbing, resource planning, artifact retention, and stage decoding. Canary results must not be generalized and do not satisfy the task.

Full success requires all 343 identities.

T104 measured that four Linux fork workers completed the comparable full replay under the repository's existing resource guard after a six-worker attempt tripped summed-RSS limits. T106 may use that retained calibration, but worker count remains an operational choice subject to the same fail-closed resource discipline. Do not relax resource guards merely to finish faster.

Native retains the GIL; thread count is not a scientific parameter and must not be used to alter bridge semantics.

## Reproducibility and Safety Checks

Before final acceptance demonstrate at least:

- exact T104 retained hashes and producer identity qualify;
- the selected identity set is exactly the accepted 343-row Part-B census in original order;
- 323/20 historical Part-B and 89/189/65 A/B/C counts are independently reconstructed from accepted evidence;
- replicate-0 seeds match T101/T104 for every identity;
- native source identity is exactly the T105-accepted pin;
- bridge call parameters are exactly frozen;
- production bridge outcome and immediately following T105 snapshot are bound to the same simulator invocation;
- structured trace schema/status/failure-code validation is strict and tested;
- Search-before-root-mapping execution order is preserved;
- exception prose cannot affect stage class or failure code;
- hidden/private extra fields are rejected;
- fixture tests cover each emitted T106 class and malformed/contradictory telemetry;
- aggregate stage counts sum exactly to 343 for success;
- historical standalone strata are not treated as monolithic stage truth;
- generated evidence is hash-bound under a T106-specific retained artifact root.

Run task-document guards, focused tests, compile/lint/format checks, changed-link checks, and `git diff --check` required by the repository. Repository-wide inherited failures may be documented and independently baseline-reproduced; do not falsely claim an all-green suite.

## Terminal Classification

Use exactly one terminal.

### `PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED`

Use only when:

- all required inputs qualify;
- all exact 343 T104 Part-B identities are replayed;
- every one reproduces its full-bridge failure under the frozen configuration;
- every replay yields a valid T105 structured trace;
- every candidate receives exactly one of the seven T106 structured stage classes;
- aggregate counts/cross-tabs are complete and auditable;
- no repair, convergence, training, or controller work occurs.

This terminal establishes first failed **control-flow stage**, not mechanics root cause and not repair efficacy.

### `T104_PART_B_BASELINE_NOT_REPRODUCED`

Use when any selected identity no longer reproduces the accepted T104 full-bridge failure under the frozen configuration and T105 native pin.

Retain the exact changed identities and evidence. Do not treat changed support as a successful stage census or as proof of improvement.

### `NATIVE_OBSERVABILITY_CONTRACT_NOT_REPRODUCED`

Use when the full-bridge failure reproduces but one or more required T105 traces are missing, malformed, unsafe, contradictory, schema-incompatible, or otherwise cannot support the contracted structured stage classification.

Do not fall back to exception-text inference.

### `INCOMPLETE`

Use when required provenance, artifacts, source identities, execution coverage, or evidence cannot be completed responsibly for reasons other than the two explicit contradiction terminals above.

## Successor Decision Boundary

T106 authorizes no repair automatically.

After final acceptance, Planner may use the exact structured stage census to select bounded successor work:

- a concentrated native-stage bucket may justify a separate diagnosis or native repair lane, depending on what the structured stage actually establishes;
- a stage label alone is not sufficient to assert the underlying mechanics defect;
- any native source modification must use the governed `sts_lightspeed` native issue/spec -> Implementer PR -> independent exact-head semantic review -> native merge -> STSRL source acceptance workflow;
- any STSRL-local adapter/validation defect must be repaired in a separate STSRL task;
- after accepted repairs materially improve N=2 support, a separate support re-entry must establish sufficient admissions before N>2 convergence can reopen.

T106 does not close T034 and does not activate T063 or T066.

## Explicit Non-Claims

T106 does not establish:

- the root cause inside any failed native stage;
- that a failure is necessarily a game-mechanics bug;
- that the 70 T104 Part-A representation-boundary cases are explained;
- that any failure has been repaired;
- that N=2 support has improved;
- particle-count sufficiency or convergence;
- exact hidden-state posterior correctness or IID sampling;
- exact `Q_public` or information-set-optimal Search;
- Battle controller/model improvement;
- complete-run improvement;
- T034 completion;
- Non-Combat improvement;
- T063/T066 authorization.

## Out of Scope

Do not perform or authorize in T106:

- replay or reinterpretation of the 70 T104 Part-A identities;
- native source modification;
- bridge/sampler/projection/mapping/Search/root-report repair;
- occurrence-mapping fallback or heuristic matching;
- exception-text causal parsing;
- exporting hidden future state;
- altered seeds, budgets, potion semantics, retry-until-pass, or N>2 execution;
- standalone sampler re-probing;
- cross-particle aggregation/action selection;
- model/student training or target generation;
- controller promotion;
- complete-run evaluation;
- T034 closure;
- Non-Combat policy work;
- T063/T066 activation.

## Material Changes Requiring Planner Amendment

Planner amendment and renewed exact-head Maintainer review are required to change any of:

- exact accepted 343-row Part-B population or ordering;
- T104 retained artifact identities/hashes;
- current T105 native pin;
- replicate-0 seed derivation;
- N=2/Search400/no-potion/unguided Search-v2 boundary;
- accepted T105 structured trace schema or stage order;
- mutually exclusive T106 classification semantics;
- baseline contradiction handling;
- prohibition on Part-A replay, repair, N>2 convergence, or training;
- terminal meanings or successor ordering.

## Acceptance and Authorization Boundary

Publishing this task does not itself authorize implementation or simulator execution.

Before implementation, Maintainer must independently review the exact task PR head and post:

```text
SPEC APPROVED

task: T106
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation/plumbing changes on the same PR do not require repeated Planner approval unless a material contract change above occurs.

Before the full 343-row simulator execution, Maintainer must confirm implementation readiness and the resource/execution plan on the then-current exact PR head. A canary may run only after implementation authorization and must remain non-generalized.

Final landing requires Maintainer final implementation/operational acceptance and Planner final scientific/architecture acceptance on the same exact final PR head.

Repair, native source change, Part-A replay, N>2 convergence, training, controller promotion, T034 closure, Non-Combat work, and T063/T066 remain unauthorized until a later task explicitly permits them.
