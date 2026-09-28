# T104: Particle-Bridge Failure Localization and Native Observability Gate

Artifact Eligibility Required: true

## Objective

Localize the accepted T103 support-domain failures without repairing them.

T103 established, on the exact frozen 413-record natural Battle-start population,
that N=2 admission remains 0/413 and that the first directly observable failure
census is:

- `PUBLIC_PROJECTION_PARITY_FAILURE`: 70/413, A/B/C = 4/3/63;
- `OPAQUE_BRIDGE_FAILURE`: 343/413, A/B/C = 89/189/65;
- all other T103 classes, including `ADMITTED`: 0.

T104 asks two bounded questions:

1. For the 70 projection-parity failures, which exact public-information fields
   drift, and does the first directly observable drift occur between the
   pre-call public projection and bridge anchor, between bridge anchor and
   particle projection, or only in a structured parity/report flag?
2. For the 343 opaque bridge failures, how far can existing accepted STSRL/native
   surfaces localize the failing stage without parsing exception prose or
   changing native behavior, and is additional native observability required?

T104 is diagnosis and observability gating only. It must not repair the sampler,
bridge, occurrence mapping, Search, public projection, restore path, or native
mechanics; it must not run particle-count convergence, train a model, or promote
any controller.

## Publication Baseline

Planner publication base:

`main @ 72b96734c33b52687aa94e36b681d4c6648b054f`

The accepted T103 scientific producer is:

`ec58e2ad396c149988ca639fd3b22244d331b9d7`

The accepted current native identity remains:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`

A native source change is a material task change and is not authorized by this
contract.

Accepted predecessors:

- T098: `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`;
- T099: `NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`, 413 attempted and 0 admitted;
- T103: `SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`, 70 projection-parity
  failures and 343 opaque bridge failures under the frozen N=2 boundary.

## Artifact Eligibility Contract

Reuse mode: `scientific_quality_claim`.

Artifact eligibility claim boundary: T104 may claim only bounded localization of
the accepted T103 failure population under the frozen T101/T103 identity and
configuration. T104 evidence is unavailable for repair efficacy, N>2 particle
convergence, controller promotion, training quality, or claims outside this
frozen cohort.

Required inputs:

- accepted T103 candidate diagnostics, aggregate report, retention manifest, and
  execution record;
- exact accepted T101/T103 413-record population and deterministic ordering;
- accepted restore/source inputs required for deterministic replay;
- current accepted native source manifest and T098/T099 capability surface;
- generated T104 per-candidate localization rows, aggregate report, and retention
  manifest.

Required predicates:

- exact artifact kind/schema/path/SHA-256 and producer provenance match accepted
  records;
- T103 input census is exactly 413 unique identities with A/B/C 93/192/128;
- accepted T103 class counts are exactly 70 projection-parity, 343 opaque, and 0
  admitted;
- current native identity equals the accepted T103 identity;
- every T104 probe is bound to one exact T103 selection identity and replicate-0
  seed;
- no T104 result is reused as a repair or convergence result.

If any required artifact, provenance fact, identity, exact retained hash, or
required qualification fact is missing, conflicting, malformed, unverifiable,
or unavailable, fail closed to `INCOMPLETE`.

## Frozen Scientific Boundary

Whenever the T099 bridge is invoked, T104 preserves:

- exact T101/T103 source identities and order;
- replicate index 0 and accepted T101 seed derivation;
- `particle_count=2`;
- `search_simulations=400`;
- `include_potions=false`;
- unchanged unguided Search v2;
- unchanged current native identity;
- no retry with altered seed/configuration to obtain a different outcome.

Independent stage probes may use fresh restored clones so one diagnostic call
cannot consume or mutate state used by another. Probe order must not change the
scientific classification.

## Baseline Reproduction Gate

Before interpreting localization results, reproduce the accepted T103 class for
each candidate re-invoked through the full T099 bridge.

If any candidate becomes admitted, or changed classifications materially
invalidate the accepted 70/343 census, terminate as:

`T103_SUPPORT_RESULT_NOT_REPRODUCED`

Do not reinterpret a changed baseline as localization evidence.

## Part A: Projection-Failure Localization

The 70 accepted `PUBLIC_PROJECTION_PARITY_FAILURE` identities form the complete
Part A census.

For each candidate retain, when the existing API exposes them:

- `P0`: canonical public projection immediately before bridge invocation;
- `A`: bridge anchor public-information projection;
- `Pi`: each returned particle public-information projection;
- existing structured public/action parity flags;
- ordered public legal-action surfaces required to interpret parity.

Each candidate receives exactly one earliest directly observable class:

1. `ANCHOR_CAPTURE_DRIFT`: `P0` is established and `A != P0`;
2. `PARTICLE_PUBLIC_STATE_DRIFT`: `A == P0` and at least one `Pi != A`;
3. `STRUCTURED_PARITY_FLAG_INCONSISTENCY`: compared public payloads are equal at
   the available boundary but a stable structured parity flag reports failure;
4. `ORDERED_PUBLIC_ACTION_DRIFT`: projection payload parity is not the earlier
   failure, but ordered public action identity/occurrence/order differs;
5. `PROJECTION_FAILURE_LOCALIZATION_OPAQUE`: accepted T103 class reproduces but
   existing public surfaces cannot responsibly distinguish the earlier classes.

For every directly observed projection mismatch retain deterministic exact
JSON-Pointer-style paths, or an equivalent canonical public-field path, including
whether each path is unequal, missing on one side, or has different stable public
value types, and whether the difference occurs in `P0 -> A`, `A -> Pi`, or both.

Do not export hidden-future payloads, hidden RNG internals, or private state.

Aggregate Part A by first-drift class, A/B/C stratum, field-path signature,
already-defined public field family, particles affected, and ordered-action
identity/occurrence/order drift. The C concentration 63/70 is descriptive
coverage, not a causal label.

## Part B: Opaque-Bridge Stage Localization

The 343 accepted `OPAQUE_BRIDGE_FAILURE` identities form the complete Part B
census.

Free-form exception text and retained RuntimeError signatures are audit/grouping
evidence only and must never determine a scientific class.

Use only existing accepted deterministic surfaces, with separate fresh clones
where needed, to probe:

1. restore/public-context/action parity;
2. accepted standalone hidden-future sampler using the same identity,
   replicate-0 seed, particle count/range, and no-potion public boundary;
3. unchanged full T099 particle/Search bridge;
4. any stable structured native/STSRL stage fields or typed codes accepted before
   T104.

Standalone sampler success proves only that standalone accepted sampler surface.
It does not prove the monolithic bridge's internal sampler passed the same stage.

### Required Part B classes

Each candidate receives the narrowest directly supported mutually exclusive
class:

1. `PRE_BRIDGE_CONTEXT_FAILURE`;
2. `STANDALONE_SAMPLER_FAILURE`;
3. `STANDALONE_SAMPLER_PUBLIC_FIDELITY_FAILURE`;
4. `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS`;
5. `STRUCTURED_MAPPING_FAILURE`;
6. `STRUCTURED_SEARCH_SETUP_OR_EXECUTION_FAILURE`;
7. `STRUCTURED_ROOT_REPORT_FAILURE`;
8. `NATIVE_STAGE_OPAQUE`.

Class 4 means the isolated sampler succeeds and the full bridge still fails, but
current evidence cannot prove a narrower internal bridge stage. It does not prove
that the monolithic bridge's own internal sampler succeeded.

These classes are evidence statements, not repair diagnoses.

## Native Observability Decision Predicate

Native-observability need is independent of the mutually exclusive Part B class.
Every Part B row must additionally retain:

- `native_observability_required`: boolean;
- `native_observability_missing_stages`: canonical ordered set drawn from the
  internal bridge stages required to distinguish the next repair boundary;
- the stable structured facts, if any, that make the boolean false.

Set `native_observability_required=true` exactly when all of the following hold:

1. the accepted full-bridge failure reproduces under the frozen configuration;
2. existing accepted structured evidence does not establish a concrete repair
   boundary inside the monolithic bridge; and
3. one or more repair-distinguishing internal outcomes remain `unknown`, such as
   monolithic hidden-future sample construction/public-fidelity validation,
   occurrence mapping, Search setup/execution, or sanitized root-report
   construction/validation.

Otherwise set it to false.

This decision must not use free-form exception prose. It must not treat an
isolated standalone sampler result as proof of a monolithic internal stage.

Consequences required by the contract:

- `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` normally has
  `native_observability_required=true` while the monolithic sampler/mapping/Search
  boundary remains unresolved;
- `NATIVE_STAGE_OPAQUE` has `native_observability_required=true` whenever the
  missing internal stage evidence is repair-distinguishing;
- directly structured mapping/Search/root-report failures may have the predicate
  false because a repair boundary is already established;
- a standalone sampler failure/fidelity failure may have the predicate false when
  that accepted surface itself is already the concrete repair boundary.

The classification and the observability predicate answer different questions
and must never be collapsed into one field.

## Native Observability Gate

Let `O` be the exact count of Part B rows with
`native_observability_required=true`.

If `O > 0`, and the T103 baseline otherwise reproduces, the successful diagnostic
terminal is:

`NATIVE_OBSERVABILITY_REQUIRED`

For that terminal retain the exact count overall and by Part B class/A-B-C
stratum, the missing-stage-set signatures, and a minimal future
`sts_lightspeed` observability requirement. The requirement describes evidence
only, for example stable non-secret stage/status codes for:

- hidden-future sample construction entered/completed;
- public-fidelity validation entered/completed;
- root occurrence mapping entered/completed/failed;
- Search setup entered;
- Search execution returned/failed;
- sanitized root-report construction entered/failed.

It must not prescribe mechanics repair or expose hidden future values. Any native
implementation occurs later through the governed `sts_lightspeed` workflow with
its own native issue/spec, Implementer PR, independent exact-head semantic review,
native merge, and later STSRL source acceptance.

T104 must not modify `sts_lightspeed`.

## Required Per-Candidate Evidence

Retain one row for every accepted T103 failure identity with at least:

- selection identity, stratum, deterministic source ordinal/digest;
- accepted T103 class and retained audit signature;
- exact current native identity and replicate-0 seed;
- probes attempted on fresh restored clones;
- baseline reproduction status for any full-bridge replay;
- Part A first-drift class and canonical public field-path differences;
- Part B narrowest stage class;
- standalone sampler success/fidelity facts;
- full bridge invocation/result status;
- structured stage facts used for classification;
- `native_observability_required` and ordered missing-stage set;
- explicit `unknown` for every internal stage not directly established;
- bounded exception type/signature for audit only;
- wall-clock and resource evidence required by the execution framework.

## Aggregate Analysis

The final report must contain exact integer counts and fractions for:

- Part A 70-candidate first-drift classes overall and by A/B/C;
- Part A field-path signatures and field families;
- Part B 343-candidate stage classes overall and by A/B/C;
- standalone sampler success/failure/fidelity counts;
- `NATIVE_STAGE_OPAQUE` coverage as a descriptive class count only;
- `native_observability_required` true/false counts overall, by Part B class and
  by A/B/C;
- canonical missing-stage-set signatures for observability-needed rows;
- retained T103 exception signatures as audit grouping only;
- candidates with a concrete repair boundary directly established;
- candidates requiring native observability before a repair can responsibly be
  specified.

The terminal decision must use the same `native_observability_required` predicate
used for these aggregate counts. It must not use `NATIVE_STAGE_OPAQUE` count as a
substitute.

No p-value, confidence interval, causal generalization, or population claim
outside the frozen T103 cohort is required.

## Reproducibility and Safety Checks

Before final acceptance demonstrate at least:

- exact T103 artifact hashes and producer identity qualify;
- exact T103 70/343/0 census and A/B/C identities reproduce from retained
  evidence;
- deterministic replicate-0 seeds match T101/T103;
- projection diffing is canonical, order-stable, and tested for nested/missing
  public fields;
- hidden/private fields cannot enter retained projection-diff output;
- exception prose cannot affect stage class or observability predicate;
- fixture tests cover each emitted T104 class;
- tests explicitly cover class4 with unresolved monolithic stages yielding
  `native_observability_required=true`;
- tests cover a structured internal failure yielding a concrete repair boundary
  and predicate false;
- standalone sampler success is not promoted to proof of monolithic internal
  sampler success;
- instrumentation does not change native call parameters or make a failing call
  pass;
- aggregate class counts sum exactly to 70 and 343 respectively;
- observability true/false counts sum exactly to 343;
- generated evidence is hash-bound under a T104-specific retained artifact root.

Run task-document guards, focused tests, compile/lint/format checks, changed-link
checks, and `git diff --check` required by the repository.

## Terminal Classification

Use exactly one terminal.

### `BRIDGE_FAILURE_LOCALIZATION_ESTABLISHED`

Use only when:

- all required inputs qualify;
- Part A is complete with auditable first-drift evidence or explicit opacity;
- all 343 Part B rows have the narrowest auditable class;
- `O == 0` under the independent observability predicate;
- existing accepted surfaces therefore define the materially relevant successor
  repair boundaries without new native observability;
- no T103 baseline contradiction is observed.

This terminal does not authorize repair or convergence re-entry.

### `NATIVE_OBSERVABILITY_REQUIRED`

Use when:

- required inputs qualify;
- Part A is completed responsibly;
- Part B is replayed/probed as specified;
- `O > 0` under the independent observability predicate, including class4 rows
  when monolithic internal stages remain unresolved;
- the exact minimal future native observability requirement is retained.

This is a successful diagnostic terminal, not an implementation failure.

### `T103_SUPPORT_RESULT_NOT_REPRODUCED`

Use when the accepted T103 support/failure baseline materially changes under the
frozen identity/configuration such that localization of the accepted census is no
longer valid.

### `INCOMPLETE`

Use when required provenance, execution identity, source coverage, qualification,
or diagnostic evidence cannot be completed responsibly.

## Successor Decision Boundary

T104 authorizes no repair automatically.

After final acceptance, Planner may choose successor work only from durable T104
evidence:

- a directly localized STSRL-local instrumentation/adapter defect may justify a
  bounded STSRL repair task;
- a localized native behavior defect requires the governed `sts_lightspeed`
  native workflow, not an STSRL implementation task;
- `NATIVE_OBSERVABILITY_REQUIRED` requires the minimal native observability lane
  before mechanics repair is specified;
- after accepted repairs materially improve support, a separate support re-entry
  task must establish sufficient N=2 admissions before any N>2 convergence
  experiment is reopened.

T063 and T066 remain non-active. T034 is not closed by T104.

## Out of Scope

Do not perform or authorize in T104:

- native source modification;
- bridge/sampler/Search/restore/public-projection mechanics repair;
- occurrence-mapping fallback or heuristic matching;
- parsing arbitrary exception prose into scientific causes;
- exporting hidden future state for diagnosis;
- altered seeds, budgets, potion semantics, or retry-until-pass behavior;
- N>2 particle-count execution or convergence/stability analysis;
- model training, checkpoint promotion, controller evaluation, or complete-run
  evaluation;
- T034 closure or T063/T066 activation.

## Material Changes Requiring Planner Amendment

Planner amendment and renewed exact-head Maintainer review are required to change
any of:

- accepted T103 70/343 population or source identities;
- current native identity;
- T101/T103 seed derivation or N=2/Search-v2@400/no-potion semantics;
- Part A first-drift classes;
- Part B stage classes;
- independent native-observability predicate or its terminal use;
- permission to use free-form exception text as a classifier;
- permission to modify native code;
- hidden/public information boundary;
- terminal meanings;
- successor authorization boundary.

Ordinary module/function names, CLI spelling, artifact filenames below a
T104-specific root, worker topology, and equivalent test mechanics remain
Maintainer/Implementer choices.

## Acceptance and Authorization Boundary

Publication of this task does not authorize implementation or scientific
execution.

Before implementation, Main Maintainer must independently review the exact task
PR head and record:

```text
SPEC APPROVED

task: T104
approved_spec_commit: <exact 40-char SHA>
implementation_authorized: true
```

After implementation/readiness review, Maintainer owns routine execution staging
within this frozen contract. A required native source or semantic change is not a
routine implementation detail and must stop this lane for Planner routing to the
native workflow.

Final landing requires Maintainer final implementation/scientific acceptance and
Planner final scientific/architecture acceptance on the same exact final PR
head.
