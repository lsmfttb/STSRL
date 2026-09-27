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

No other open STSRL task PR exists at publication.

The accepted T103 scientific producer is:

`ec58e2ad396c149988ca639fd3b22244d331b9d7`

The accepted current native identity remains:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`

with the accepted binary/source binding retained by the T103 evidence record.
A native source change is a material task change and is not authorized by this
contract.

Accepted predecessors:

- T098: `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`;
- T099: `NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`, 413 attempted and 0 admitted;
- T103: `SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`, 70 projection-parity
  failures and 343 opaque bridge failures under the frozen N=2 boundary.

## Artifact Eligibility Contract

Required inputs:

- the accepted T103 candidate diagnostics, aggregate report, retention manifest,
  and execution record;
- the exact accepted T101/T103 413-record population and deterministic ordering;
- the accepted restore/source inputs required for deterministic replay;
- the current accepted native source manifest and T098/T099 capability surface;
- generated T104 per-candidate localization rows, aggregate report, and retention
  manifest.

Reuse mode: `scientific_quality_claim`, limited to localization of the accepted
T103 failure population.

Required predicates:

- exact artifact kind/schema/path/SHA-256 and producer provenance match accepted
  records;
- the T103 input census is exactly 413 unique identities with A/B/C 93/192/128;
- the accepted T103 class counts are exactly 70 projection-parity, 343 opaque,
  and 0 admitted;
- the current native identity equals the accepted T103 identity;
- every T104 probe is bound to one exact T103 selection identity and replicate-0
  seed;
- no T104 result is used as a repair or convergence result.

If any required artifact, provenance fact, identity, or exact retained hash is
missing, conflicting, malformed, or unverifiable, fail closed to `INCOMPLETE`.

## Frozen Scientific Boundary

T104 preserves the T103 scientific configuration wherever the T099 bridge is
invoked:

- exact T101/T103 source identities and order;
- replicate index 0 and accepted T101 seed derivation;
- `particle_count=2`;
- `search_simulations=400`;
- `include_potions=false`;
- unchanged unguided Search v2;
- unchanged current native identity;
- no retry with altered seed/configuration to obtain a different outcome.

T104 may use fresh restored clones for independent stage probes so one diagnostic
call cannot consume or mutate state used by another. Probe order itself must not
change the scientific classification.

## Baseline Reproduction Gate

Before interpreting localization results, reproduce the accepted T103 class for
each candidate that is re-invoked through the full T099 bridge.

If a full-bridge replay changes a candidate from its accepted T103 top-level
class, stop interpretation for that candidate and record the exact mismatch.
If any candidate becomes admitted, or if changed classifications are broad enough
to invalidate the accepted 70/343 census, terminate as:

`T103_SUPPORT_RESULT_NOT_REPRODUCED`

Do not silently reinterpret a changed baseline as new localization evidence.

## Part A: Projection-Failure Localization

The 70 accepted `PUBLIC_PROJECTION_PARITY_FAILURE` candidates form a complete
census for Part A.

For each of the 70, capture only accepted public-information surfaces and retain
three logically distinct projections when the existing API exposes them:

- `P0`: the canonical public projection immediately before bridge invocation;
- `A`: the bridge anchor public-information projection;
- `Pi`: each returned particle public-information projection.

Also retain the existing structured public/action parity flags and the ordered
public legal-action surfaces needed to interpret projection consistency.

### Required first-drift classes

Each of the 70 must receive exactly one earliest directly observable class:

1. `ANCHOR_CAPTURE_DRIFT`
   - `P0` is established and `A != P0` before any particle-vs-anchor drift is
     needed to explain failure;
2. `PARTICLE_PUBLIC_STATE_DRIFT`
   - `A == P0` is established and at least one `Pi != A`;
3. `STRUCTURED_PARITY_FLAG_INCONSISTENCY`
   - compared public payloads are equal at the available boundary but a stable
     structured parity flag reports failure;
4. `ORDERED_PUBLIC_ACTION_DRIFT`
   - projection payload parity is not the earlier failure, but ordered public
     legal-action identity/occurrence/order differs at a directly observed stage;
5. `PROJECTION_FAILURE_LOCALIZATION_OPAQUE`
   - the accepted T103 class reproduces but existing public surfaces cannot
     responsibly distinguish the earlier classes.

The implementation may use more detailed stable subreason codes, but every
subreason must map to exactly one class above.

### Field-level evidence

For every structurally observed projection mismatch, retain deterministic exact
JSON-Pointer-style differing paths or an equivalent canonical public-field path
representation. Report:

- path present on both sides but unequal;
- path missing on one side;
- stable public value type on each side;
- whether the difference occurs in `P0 -> A`, `A -> Pi`, or both.

Public values may be retained only when already permitted by the accepted public
projection contract. Hidden-future payloads, hidden RNG internals, or private
state must not be exported merely to explain a difference.

Aggregate Part A by:

- first-drift class;
- A/B/C stratum;
- exact field-path signature;
- field family where an already-defined public schema provides one;
- number of particles affected per candidate;
- whether ordered action identity/occurrence/order also differs.

The concentration of 63/70 accepted T103 projection failures in cohort C is a
fact to explain descriptively, not permission to infer a cause from cohort label
alone.

## Part B: Opaque-Bridge Stage Localization

The 343 accepted `OPAQUE_BRIDGE_FAILURE` candidates form a complete census for
Part B.

T104 must not convert the retained two RuntimeError signatures or any other
free-form exception text into causal labels. Exact exception type/signature may
be used only as an audit/grouping key.

Use only existing accepted deterministic surfaces to establish stage reach. At
minimum evaluate, where technically available without native modification:

1. restore/public-context/action parity on a fresh clone;
2. the accepted standalone hidden-future sampler capability using the same
   selection identity, replicate-0 seed, particle count/range, and no-potion
   public-information boundary;
3. the unchanged full T099 particle/Search bridge on a separate fresh clone;
4. any already-existing structured native/STSRL stage fields or stable typed
   error codes accepted before T104.

A standalone sampler probe may establish only facts about that standalone
accepted sampler surface. It must not be treated as proof that a monolithic
bridge internally passed an identical stage unless the existing API contract
explicitly establishes that equivalence.

### Required opaque-stage classes

Each of the 343 must receive the narrowest directly supported class from:

1. `PRE_BRIDGE_CONTEXT_FAILURE`
   - accepted restore/public context/action completeness no longer reproduces;
2. `STANDALONE_SAMPLER_FAILURE`
   - the frozen standalone accepted sampler probe itself fails before producing
     its accepted sanitized output;
3. `STANDALONE_SAMPLER_PUBLIC_FIDELITY_FAILURE`
   - standalone sampler returns but its accepted public-fidelity predicates fail;
4. `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS`
   - standalone sampler succeeds on the isolated probe, full bridge still fails,
     but current observability cannot prove a narrower internal bridge stage;
5. `STRUCTURED_MAPPING_FAILURE`
   - an already-existing stable structured field/type directly establishes the
     occurrence-mapping boundary;
6. `STRUCTURED_SEARCH_SETUP_OR_EXECUTION_FAILURE`
   - an already-existing stable structured stage proves mapping passed/reached
     sufficiently and Search setup/execution failed;
7. `STRUCTURED_ROOT_REPORT_FAILURE`
   - an already-existing stable structured stage proves Search returned/reached
     sufficiently and root-report construction/validation failed;
8. `NATIVE_STAGE_OPAQUE`
   - the full bridge failure reproduces and no existing accepted structured
     evidence supports a narrower internal stage.

These classes are evidence statements, not repair diagnoses. In particular,
`BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` does not prove that the
monolithic bridge's own internal sampler succeeded.

## Native Observability Gate

T104 must explicitly decide whether the remaining opaque population can be
localized enough for a concrete repair task using existing accepted surfaces.

If one or more materially important bridge failures remain `NATIVE_STAGE_OPAQUE`
and no stable existing stage surface can distinguish the relevant internal
boundary, the normal terminal may be:

`NATIVE_OBSERVABILITY_REQUIRED`

For that terminal, produce an exact minimal observability requirement for a
future `sts_lightspeed` native issue/spec. The requirement must describe only
what evidence is missing, for example stable non-secret stage/status codes such
as:

- hidden-future sample construction entered/completed;
- public-fidelity validation entered/completed;
- root occurrence mapping entered/completed/failed;
- Search setup entered;
- Search execution returned/failed;
- sanitized root-report construction entered/failed.

The requirement must not prescribe a repair to mechanics and must not expose
hidden future values. Any implementation of new native observability must occur
later through the governed `sts_lightspeed` workflow, with its own issue/spec,
native Implementer PR, independent exact-head semantic review, native merge,
and subsequent STSRL source acceptance.

T104 itself must not modify `sts_lightspeed`.

## Required Per-Candidate Evidence

Retain one T104 row for every accepted T103 failure identity, containing at least:

- `selection_identity`, stratum, deterministic source ordinal/digest;
- accepted T103 class and retained T103 audit signature;
- exact current native identity and replicate-0 sampler seed;
- which T104 probes were attempted on fresh restored clones;
- baseline reproduction status for any full-bridge replay;
- Part A first-drift class and field-path differences when applicable;
- Part B narrowest structured stage class when applicable;
- standalone sampler success/fidelity facts when applicable;
- full bridge invocation/result status;
- structured stage facts used for classification;
- bounded exception type/signature for audit only;
- explicit `unknown` for every internal stage not directly established;
- wall-clock and resource evidence required by the execution framework.

## Aggregate Analysis

The final report must contain exact integer counts and fractions for:

- Part A 70-candidate first-drift classes overall and by A/B/C;
- Part A exact field-path signatures and field families;
- Part B 343-candidate stage classes overall and by A/B/C;
- standalone sampler success/failure/fidelity counts for Part B;
- `NATIVE_STAGE_OPAQUE` coverage;
- counts by retained T103 exception signature as audit grouping only;
- number of candidates for which a concrete STSRL-local repair boundary is
  directly established;
- number requiring native observability before a repair can be responsibly
  specified.

No p-value, confidence interval, causal generalization, or population claim
outside the frozen T103 cohort is required.

## Reproducibility and Safety Checks

Before final acceptance demonstrate at least:

- exact T103 artifact hashes and producer identity qualify;
- exact T103 70/343/0 census and A/B/C identities are reproduced from retained
  evidence before T104 execution;
- deterministic replicate-0 seeds match T101/T103;
- projection diffing is canonical, order-stable, and tested for nested/missing
  public fields;
- hidden/private fields cannot enter retained projection-diff output;
- exception prose cannot affect scientific stage classification;
- synthetic/fixture tests cover each T104 class that implementation can emit;
- an opaque bridge failure remains opaque when structured evidence is absent;
- standalone sampler success is not incorrectly promoted to proof of internal
  monolithic-bridge sampler success;
- instrumentation does not change native call parameters or make a failing
  bridge call pass;
- aggregate counts sum exactly to 70 and 343 respectively;
- generated evidence is hash-bound under a T104-specific retained artifact root.

Run ordinary task-document guards, focused tests, compile/lint/format checks,
changed-link checks, and `git diff --check` required by the repository.

## Terminal Classification

Use exactly one terminal:

### `BRIDGE_FAILURE_LOCALIZATION_ESTABLISHED`

Use when:

- all required inputs qualify;
- all 70 projection failures have an auditable first-drift class and field-level
  evidence or explicit projection-localization opacity;
- all 343 opaque failures have the narrowest auditable stage class;
- existing accepted surfaces localize the materially relevant failures enough to
  define successor repair boundaries without adding native observability;
- no T103 baseline contradiction is observed.

This terminal does not authorize any repair or convergence re-entry.

### `NATIVE_OBSERVABILITY_REQUIRED`

Use when:

- required inputs qualify;
- Part A is completed responsibly;
- Part B is replayed/probed as specified;
- materially important failures remain `NATIVE_STAGE_OPAQUE` because the current
  accepted API does not expose a stable structured internal stage;
- the exact minimal future native observability requirement is retained.

This is a successful diagnostic terminal, not an implementation failure.

### `T103_SUPPORT_RESULT_NOT_REPRODUCED`

Use when the accepted T103 support/failure baseline materially changes under the
frozen identity/configuration such that localization of the accepted census is no
longer valid.

### `INCOMPLETE`

Use when required provenance, execution identity, source coverage, or diagnostic
evidence cannot be completed responsibly.

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
- after accepted repairs materially improve the support boundary, a separate
  support re-entry task must establish sufficient N=2 admissions before any
  N>2 particle-convergence experiment is reopened.

T063 and T066 remain non-active. T034 is not closed by T104.

## Out of Scope

Do not perform or authorize in T104:

- native source modification;
- bridge/sampler/Search/restore/public-projection mechanics repair;
- occurrence-mapping fallback or heuristic matching;
- parsing arbitrary exception prose into scientific causes;
- exporting hidden future state for diagnosis;
- altered seeds, budgets, potion semantics, or retry-until-pass behavior;
- N>2 particle-count execution;
- convergence/stability analysis;
- model training, checkpoint promotion, controller evaluation, or complete-run
  evaluation;
- T034 closure or T063/T066 activation.

## Material Changes Requiring Planner Amendment

Planner amendment and renewed exact-head Maintainer review are required to change
any of:

- the accepted T103 70/343 population or source identities;
- current native identity;
- T101/T103 seed derivation or N=2/Search-v2@400/no-potion semantics;
- Part A first-drift classes;
- Part B opaque-stage classes;
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
