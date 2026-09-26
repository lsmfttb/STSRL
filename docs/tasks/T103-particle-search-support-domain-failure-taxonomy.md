# T103: Natural Battle-Start Particle/Search Support-Domain Failure Taxonomy

Artifact Eligibility Required: true

## Objective

Explain the accepted T101 result that **0 of 413** natural Battle-start candidates
satisfied the frozen N=2 T099 particle/Search bridge admission boundary.

T103 asks one bounded diagnostic question:

> Across the exact T101 413-record A/B/C source population, which earliest
> observable support boundary prevents each candidate from satisfying the
> unchanged T101 N=2 admission contract, and what exact failure distribution
> does that produce?

This task is diagnosis only. It must not repair the bridge, change Search,
change native mechanics, weaken fail-closed mapping semantics, run particle
convergence, train a model, or promote a controller.

T101 established only `SUPPORTED_COHORT_INSUFFICIENT`: all 413 candidates were
attempted, zero were admitted, and no canary/formal convergence evidence exists.
A separate bounded diagnosis of the first hash-ordered A/B/C candidate observed
the native T099 incomplete/ambiguous Search-v2 occurrence-mapping boundary on
those **three samples only**. T103 must not assume that cause applies to the
remaining 410 candidates.

## Publication Baseline

Planner publication base:

`main @ 56259175e5616ff334c6b74fa4e70d141df26783`

No other open STSRL task PR exists at publication.

The canonical native integration identity remains owned by
`docs/sts_lightspeed_source_manifest.json` and at publication resolves to:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`

A native source change is a material task change and is not authorized by this
contract.

Accepted predecessors:

- T087/T088: exact 413-record matched natural Battle-start population with
  A/B/C counts `93/192/128`, accepted restore/source provenance, and frozen
  unguided Search v2 @400 Battle baseline;
- T098: `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY` on its accepted support
  boundary;
- T099: `NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`, with all 413 candidates attempted and
  zero admitted;
- T102: `AGENT_PLANNER_REVIEW_ROUTING_ESTABLISHED`, governing routine
  Planner-actionable review notification.

The accepted T101 terminal retention manifest is retained under
`artifacts/t101-bounded-particle-convergence-361a77d/admission/` with schema
`t101-terminal-retention-manifest-v1` and SHA-256:

`922ef003d2fa15dea57f59c71fa99bfb6f5a418d48026b04ed3019d7e6cf4f97`

## Artifact Eligibility Contract

Required scientific inputs:

- the exact accepted T087/T088 413-record source population and ordering facts;
- the exact retained restore/source artifacts required to replay those records;
- the accepted T101 input-admission/cohort-attempt/terminal-retention evidence;
- the current native source manifest and accepted T099 bridge capability;
- generated T103 per-candidate diagnostic rows, aggregate report, and retention
  manifest.

Reuse mode: `scientific_quality_claim`, narrowly limited to explaining the
support-domain failure distribution of the exact frozen T101 admission boundary.

Claim boundary: T103 may claim only which **observable first-failing boundary**
was established for each replayed candidate and the resulting exact counts by
stratum and diagnostic class. It must not claim hidden root cause beyond the
available evidence, convergence/non-convergence, posterior correctness,
controller quality, Search improvement, or general support outside the frozen
413-record population.

Required predicates:

- exact artifact kind/schema/path/SHA-256 and producer provenance match accepted
  records;
- the source population is exactly 413 unique accepted selection identities with
  A/B/C counts `93/192/128`;
- T101 retained evidence confirms every source candidate was attempted and zero
  were admitted under the accepted terminal;
- current execution uses the exact manifest-selected native identity above;
- retained historical producer identities are not rewritten as current-native
  producer facts;
- each T103 replay preserves the exact source identity, stratum, and
  deterministic T101 ordering;
- diagnostic evidence is recorded before any interpretation or successor
  recommendation.

Unavailable behavior: if a required provenance fact, source record, retained
T101 identity, native identity, or diagnostic field is missing, conflicting,
malformed, or unverifiable, fail closed to `INCOMPLETE`. Do not infer eligibility
from filenames, local paths, or successful parsing.

## Frozen Replay Boundary

T103 replays the exact support question from T101; it does not invent a new
admission surface.

For every one of the 413 source records, in the exact deterministic per-stratum
order used by T101:

1. restore the exact accepted Battle-start record with the same current-native
   consumer boundary used by T101;
2. derive sampler seed using the accepted T101 replicate-0 seed derivation from
   `selection_identity`;
3. invoke the same T099 bridge admission configuration:
   - `particle_count=2`;
   - `search_simulations=400`;
   - `include_potions=false`;
   - unchanged unguided Search v2;
4. do not inspect Search values, rankings, Battle outcomes, or hidden-diversity
   magnitude to choose or skip records;
5. retain exactly one diagnostic result for every source identity.

The replay is single-purpose diagnostic execution. No N=4/8/16/32 call is
authorized. No formal T101 convergence run is authorized.

### Baseline reproducibility gate

T103 expects to reproduce T101's support result: zero admitted candidates.

If any candidate newly satisfies the complete frozen admission boundary, stop
scientific interpretation and terminate as:

`T101_SUPPORT_RESULT_NOT_REPRODUCED`

The report must identify every changed candidate and the exact current/retained
execution identities. Do not continue to a failure-frequency conclusion when
the baseline support result itself changed.

## Observable First-Failing Boundary

For each candidate, record the **earliest boundary for which failure is directly
established by available evidence**. Later boundaries are `NOT_REACHED`; they
must not be guessed.

The required top-level diagnostic classes are:

1. `RESTORE_OR_SOURCE_BINDING_FAILURE`
   - accepted record cannot be restored/bound under the frozen current-native
     consumer boundary;
2. `PUBLIC_PROJECTION_PARITY_FAILURE`
   - restored public projection differs from the accepted public state;
3. `ORDERED_LEGAL_ACTION_PARITY_FAILURE`
   - ordered public legal-action occurrence surface differs;
4. `BRIDGE_PRECONDITION_OR_SAMPLER_FAILURE`
   - T099 bridge/sampler fails before a more specific root-mapping/Search
     boundary is directly observable;
5. `ROOT_OCCURRENCE_MAPPING_INCOMPLETE`
   - existing evidence directly establishes incomplete public-occurrence to
     Search-edge/equivalence coverage;
6. `ROOT_OCCURRENCE_MAPPING_AMBIGUOUS`
   - existing evidence directly establishes ambiguous occurrence mapping;
7. `ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS`
   - the accepted/native error surface directly establishes this combined
     boundary but does not support responsibly separating the two cases;
8. `SEARCH_EXECUTION_FAILURE`
   - occurrence mapping is established sufficiently to enter Search, but the
     unchanged Search-v2@400 continuation fails before a valid report;
9. `NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES`
   - Search returns but required finite root evidence fails the frozen
     admission predicate;
10. `OPAQUE_BRIDGE_FAILURE`
    - the bridge fails and existing observable evidence cannot responsibly
      localize the failure to a more specific class;
11. `ADMITTED`
    - the complete T101 N=2 structural admission boundary succeeds.

Implementation may use a more detailed `subreason_code`, but every subreason
must map to exactly one top-level class above.

### Evidence discipline

- Classify from explicit API stage, structured field, stable exception type/code,
  or another directly retained observation.
- Raw exception class and a bounded normalized message/signature may be retained
  for audit.
- Do **not** convert arbitrary free-form exception text into a scientific class
  unless implementation demonstrates that the exact text is a stable contract
  of the frozen boundary.
- Do **not** reproduce native mechanical-equivalence logic in Python merely to
  force a more specific category.
- If the current bridge surface cannot distinguish incomplete from ambiguous,
  use the combined class rather than guessing.
- If no specific class is justified, use `OPAQUE_BRIDGE_FAILURE`.

The task values honest opacity over false precision.

## Diagnostic Instrumentation Boundary

T103 may add STSRL-side diagnostic plumbing needed to preserve already-existing
stage/error information, provided it does not change the success/failure outcome
of the frozen T101 admission call.

Allowed examples:

- preserve exception cause chains instead of replacing them with one generic
  T101 exclusion string;
- record which existing validation stage raised;
- normalize existing structured error codes/types into the frozen taxonomy;
- add tests proving classification does not alter bridge behavior.

Not authorized:

- changing `sts_lightspeed` source or native behavior;
- changing T099 occurrence-equivalence semantics;
- weakening incomplete/ambiguous mapping rejection;
- adding fallback mappings or ordinal guesses;
- changing public projection, legal actions, sampler behavior, Search policy,
  Search budget, or action-space semantics;
- retrying with altered seeds/configurations until a state passes.

If useful diagnosis requires new native observability, stop and classify the
missing observability. A future native issue/PR must use the governed
`sts_lightspeed` workflow; T103 must not implement that native change in STSRL.

## Required Per-Candidate Evidence

Retain one row per source identity containing at least:

- `selection_identity`;
- stratum A/B/C;
- deterministic source ordinal / selection digest;
- exact historical source/provenance bindings required for replay;
- exact current native identity;
- deterministic replicate-0 sampler seed;
- `particle_count=2`, `search_simulations=400`, `include_potions=false`;
- restore method or directly observed restore failure;
- projection-parity status;
- ordered-legal-action-parity status;
- bridge-invocation status;
- top-level first-failing diagnostic class;
- optional stable subreason code;
- exception type / bounded normalized audit signature where applicable;
- whether occurrence mapping was reached and, if directly known, whether it was
  complete/ambiguous;
- whether Search execution was reached;
- whether a valid finite required root report was reached;
- wall-clock duration for the attempted diagnostic call;
- `admitted` boolean.

No hidden future payload may be exported beyond fields already accepted by
T098/T099. Diagnostic fields are evidence only and must not become model or
controller inputs.

## Required Aggregate Analysis

The final report must include exact integer counts and fractions for:

- all 413 candidates;
- each A/B/C stratum separately;
- each top-level diagnostic class;
- each stable subreason code where present;
- `OPAQUE_BRIDGE_FAILURE` coverage;
- occurrence-mapping-related classes combined;
- candidates reaching Search execution;
- candidates reaching a valid finite root report;
- admitted candidates.

Also report the most frequent exact diagnostic signatures without collapsing
semantically different failures merely because their prose looks similar.

No p-value, confidence interval, causal language, or population-generalization
claim is required. This is a census of the frozen 413-record support population,
not a statistical sample of all possible STS Battle states.

## Reproducibility Checks

Before final acceptance, demonstrate at least:

- exact 413-record identity/order and A/B/C counts match T101;
- deterministic T101 sampler seeds are reproduced;
- repeated classification of a bounded fixture set is deterministic;
- each synthetic/fixture boundary maps to the intended top-level class;
- incomplete and ambiguous are not separated when only combined evidence exists;
- opaque failure remains opaque rather than being guessed;
- classifier/instrumentation does not change a successful accepted bridge report;
- classifier/instrumentation does not make a previously failing bridge call pass;
- aggregate counts sum exactly to 413 and per-stratum sums are 93/192/128;
- generated evidence is hash-bound and retained under a T103-specific artifact
  directory.

Ordinary repository tests, task-document guards, changed-link checks, and
`git diff --check` must also pass. If Python code is added, run the relevant
focused pytest plus compile/lint/format checks required by the repository.

## Terminal Classification

Use exactly one terminal:

### `SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`

Use when:

- all required inputs are qualified;
- all 413 candidates are replayed exactly once under the frozen diagnostic
  configuration;
- zero candidates are admitted, reproducing T101;
- every candidate has one auditable top-level class, including explicit opaque
  classification where necessary;
- aggregate counts and retained evidence are complete.

This terminal does **not** mean the root cause is fully localized. The final
report must separately state how much of the 413-record population remains
opaque and the exact distribution of known classes.

### `T101_SUPPORT_RESULT_NOT_REPRODUCED`

Use when one or more candidates newly pass the complete frozen admission
boundary. Stop before interpreting failure frequencies.

### `INCOMPLETE`

Use when required provenance, execution identity, source coverage, or diagnostic
evidence cannot be completed responsibly.

## Successor Decision Boundary

T103 itself authorizes no repair.

After the terminal report, Planner may choose a successor only from durable
T103 evidence:

- a well-localized native capability gap may justify a separately governed
  `sts_lightspeed` issue/spec/implementation/review/merge lane;
- a clearly STSRL-local diagnostic/adapter bug may justify a bounded STSRL repair
  task;
- a genuinely mixed support domain may require prioritizing the smallest
  high-coverage capability gap before any T101 re-entry;
- predominantly opaque evidence may justify an observability task rather than a
  mechanics repair;
- a changed/nonzero support result requires reproducibility investigation before
  convergence work.

Do not reopen T101 particle convergence merely because T103 completes. A future
T101-style re-entry requires an explicit new task after the relevant support
boundary has been accepted and independently verified.

T063 and T066 remain non-active. T103 does not promote training, Non-Combat,
complete-run, or live deployment work.

## Out Of Scope

Do not perform or authorize in T103:

- native source modification;
- Search-v2 algorithm/configuration modification;
- T099 bridge semantic repair;
- occurrence-mapping fallback or heuristic matching;
- N>2 particle-count execution;
- convergence/stability analysis;
- cross-particle action aggregation/execution;
- model training or checkpoint promotion;
- T034 closure;
- T063/T066 activation;
- controller or complete-run evaluation.

## Material Changes Requiring Planner Amendment

Planner amendment and renewed exact-head Maintainer review are required to
change any of:

- the exact 413-record source population or ordering;
- current native source identity;
- T101 seed derivation;
- N=2 / Search-v2@400 / no-potion admission semantics;
- top-level diagnostic taxonomy or first-failing-boundary rule;
- evidence discipline allowing inferred/heuristic causes;
- permission to modify native code or bridge success semantics;
- baseline reproducibility gate;
- terminal meanings;
- successor authorization boundary.

Ordinary module/function names, CLI spelling, artifact filenames below the
T103-specific directory, worker topology, logging layout, and equivalent test
mechanics remain Maintainer/Implementer choices.

## Acceptance And Authorization Boundary

Publication of this task does not authorize implementation or scientific
execution.

Before implementation, Main Maintainer must independently review the exact task
PR head and record:

```text
SPEC APPROVED

task: T103
approved_spec_commit: <exact 40-char SHA>
implementation_authorized: true
```

After implementation/readiness review, Maintainer owns any routine execution
staging required by the contract. Planner should be contacted before execution
only for a genuine material scientific/architecture gap, not for ordinary
canary/readiness authorization.

Final landing requires Maintainer final implementation/scientific acceptance and
Planner final scientific/architecture acceptance on the same exact final PR
head.