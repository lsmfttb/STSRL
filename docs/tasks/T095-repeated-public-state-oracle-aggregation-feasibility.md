# T095: Repeated-Public-State Oracle Aggregation Feasibility Audit

Artifact Eligibility Required: true

## Objective

Test whether the exact retained T092 internal Search telemetry already contains
a reproducible empirical signal for the research idea now selected after T094:

> when the same public Battle state/action set is observed under multiple
> hidden/full-simulator realizations, do not delete differing Oracle-conditioned
> action values as "conflicts"; instead treat them as conditional observations
> and ask whether equal-source aggregation produces a stable public-state action
> preference.

T095 is deliberately an **offline feasibility audit**, not a normal-information
teacher implementation.

It asks only whether the currently observed repeated-public-state surface is
large and stable enough to justify the next architectural investment in an
authoritative public-consistent hidden-future sampler (the blocked T034
direction).

T095 does **not** claim that the retained repeated occurrences are IID samples
from the true hidden-future posterior, that averaging current Oracle Search
values produces an information-set-optimal no-SL Q-value, or that any student
model should yet be trained from these aggregates.

## Publication Baseline

Publication base:

`main @ 74264c564011ca5bcffed710e8e42ff0600cf8dc`

Accepted T092 lineage:

- validated implementation/evidence head:
  `1e3dff2665d38dfd6acc786666c1889bc8327508`;
- formal evidence SHA-256:
  `ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a`;
- retention manifest SHA-256:
  `32f4b04f31c91cf58928503d51023ba53c98f310bcb96644503040b2fd9d18b7`;
- retained artifact root:
  `/mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-formal-413-1e3dff2-20260918/`;
- exact source ledger A/B/C = `93/192/128`;
- frozen teacher = unguided Search-v2@400;
- retained internal occurrences = `1,656,822` depth>=1 occurrences.

Accepted T094 lineage:

- final PR head:
  `95c86b43304f113697551a0732f75bbc87b0f863`;
- merge commit:
  `74264c564011ca5bcffed710e8e42ff0600cf8dc`;
- terminal classification:
  `A_COHORT_CANONICALIZATION_LIMITING`;
- report SHA-256:
  `bad75c299da9345df6aa02a0235411a8718e776f5ad9772b5d9bde5fe7722d88`;
- retention-manifest SHA-256:
  `283ef46a4eace93a515e57a7676cdc02bcfc57acf477146b4f35d0bd378082e8`;
- retained artifact root:
  `/mnt/d/DeadlyCatCoding/STSRL/artifacts/t094-a-cohort-supervision-attrition-6c81b8c-20260918/`.

T094 established that all 93 A starts already have at least one pre-dedup
`n_min=4` pair-bearing public state, and that the large A loss occurs only
after public-fingerprint leakage/canonicalization treatment. That result
motivates T095 but does not itself define the aggregation target.

## Research Semantics

### What one repeated public state means

Use the accepted T092 public fingerprint:

```text
(public-tactical-v2 student-visible Battle state,
 ordered teacher-searchable public action identities)
```

Two occurrences with the same fingerprint are indistinguishable under this
student-visible representation, even if their private simulator state, hidden
draw order, RNG state, Search path, or other hidden future facts differ.

T095 treats different Oracle-conditioned values attached to such repeated
public states as **observed conditional variation**, not as invalid labels.

### What T095 may estimate

For one repeated public fingerprint `x` and one deterministic unordered public
action pair `(a,b)`, each accepted occurrence with both actions supported at
`n_min=4` supplies:

```text
delta_occurrence = teacher_mean(x, hidden realization, a)
                 - teacher_mean(x, hidden realization, b)
```

The sign convention is fixed by deterministic public action identity ordering,
not by which action the teacher preferred in that occurrence.

T095 may estimate only the **observed empirical distribution** of these deltas
and an equal-source-start aggregate over the retained T092 occupancy.

It must not call this quantity the true
`E[Q | public information]`, a normal-information optimal action value, or a
posterior expectation.

### Two unresolved gaps remain explicit

Even a positive T095 result leaves both of these unresolved:

1. **Sampling gap.** T092 repeats were encountered through the accepted
   Search/trajectory process. They were not drawn by an authoritative sampler
   from `P(hidden future | public state and public history)`.
2. **Continuation-information gap.** The retained child means come from
   full-simulator-state Oracle-like Search. After the current action, the
   continuation Search still has privileged information. Averaging those means
   therefore need not equal the value of a continuation policy that remains
   public-only.

These are exactly why T095 can motivate T034 but cannot close T034.

A separate downstream value problem also remains: the final project objective is
eventual A20 Heart success, not merely current-Battle win probability. T095 does
not alter the frozen T092 terminal utility or solve Battle-to-run continuation
value.

## Artifact Eligibility Contract

### Inputs

Use only the exact accepted T092 retained formal evidence, retention manifest,
source records, and internal occurrences named above.

The accepted T094 report/manifest may be used only to verify lineage and the
already-landed attrition result.

No new Search execution, Battle replay, hidden-future resampling, source
recollection, substitute corpus, checkpoint restore, or simulator call is
eligible.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T095 may claim only:

- how many repeated public fingerprints and public action pairs have support
  across distinct accepted source starts;
- the observed Oracle-conditioned value/preference variation on those repeats;
- whether an equal-source-start empirical aggregate is reproducible under the
  preregistered split-half stability test; and
- whether this empirical surface is sufficiently broad and stable to justify a
  separately specified T034/public-consistent-hidden-future-sampler investment.

T095 may not claim:

- true hidden-future posterior sampling;
- information-set-optimal or no-SL-optimal action values;
- unbiased Q-values;
- policy improvement;
- student learnability;
- Battle controller improvement;
- complete-run improvement;
- deployment readiness;
- T034 closure; or
- T066 authorization.

### Required predicates

- exact T092 evidence, retention, source-record and source-ledger identities
  validate;
- all 413 accepted source starts preserve source group and inherited provenance;
- only accepted stable depth>=1 T092 public decision occurrences are used;
- public fingerprint and teacher-searchable action identities are exactly the
  accepted T092 schema;
- primary action support remains frozen at `n_min=4`;
- each pair delta uses finite accepted T092 child means for both actions;
- no hidden/private field enters grouping, weighting, split-half assignment,
  or any candidate public target;
- source start, not raw occurrence count, is the primary aggregation unit;
- disagreement signs are retained and reported rather than deleted;
- all deterministic ordering/splitting uses only public fingerprint, public
  action identities, source identity, and a frozen domain separator, never
  teacher values.

### Unavailable-fact behavior

Missing, malformed, conflicting, inferred, filename-derived, regenerated,
substitute, or unverifiable material facts fail closed to `INCOMPLETE`.

## Aggregation Unit

### Occurrence-level observation

For every public fingerprint and every unordered pair of teacher-searchable
actions where both actions have:

- child visits >= 4;
- finite teacher mean;

retain the signed pair delta under deterministic action-identity ordering.

Teacher ties with `abs(delta) <= 1e-9` are retained as zero/tie observations
for distribution reporting but do not count as positive or negative signs.

### Source-start macro cell

Multiple eligible occurrences of the same
`(public fingerprint, action pair, source start)` must not give that source
start extra weight merely because Search revisited the state more often.

Collapse them to one source-start macro cell:

```text
source_cell_delta =
    arithmetic mean of all eligible occurrence deltas
    for this (fingerprint, action pair, source start)
```

Retain the within-source occurrence count, mean, minimum, maximum, and sign
composition descriptively.

Every distinct source start then contributes weight exactly 1 to the primary
cross-source aggregate.

This macro weighting is a correlation guard, not a claim that different source
starts are IID hidden-future posterior samples.

## Repeated-State Support Surface

For each public fingerprint and action pair, report the number of distinct
source-start macro cells.

Report coverage at:

`k_min in {2, 4, 8, 16}`

where `k_min` is the minimum distinct-source-start count for one aggregate
pair.

The primary feasibility surface is `k_min=8`, chosen so the deterministic
stability test below can compare two halves containing at least four source
starts each.

Report separately:

- distinct repeated public fingerprints;
- distinct fingerprint/action-pair aggregates;
- A-only, B-only, C-only, and mixed-source-group support;
- distribution of distinct-source counts;
- occurrence multiplicity per source macro cell.

No original T090/T093 train/validation/heldout ownership is used as a learning
split in T095.

## Observed Conditional-Variation Metrics

For every primary `k_min=8` aggregate pair report, over equal-weight
source-start macro cells:

- source-start count;
- arithmetic mean delta;
- median delta;
- standard deviation;
- minimum and maximum;
- positive / tie / negative source-cell counts;
- positive fraction among non-ties;
- whether both positive and negative source-cell signs occur.

A pair with at least one positive and one negative source-cell delta is an
**observed conditional-variation pair**.

This term is descriptive. T095 must not infer which hidden fact caused the
variation.

## Deterministic Split-Half Stability Test

For each primary aggregate pair with `N >= 8` distinct source starts:

1. compute SHA-256 over the frozen domain separator
   `T095-PUBLIC-AGGREGATION-SPLIT-V1`, public fingerprint, deterministic
   action-pair identity, and source identity;
2. sort source-start macro cells by that hash;
3. assign alternating sorted cells to half 0 and half 1, yielding half sizes
   differing by at most one;
4. compute the equal-source mean delta in each half and in the full set.

An aggregate pair is **direction-stable** only when:

- full-set mean has `abs(mean) > 1e-9`;
- both half means have `abs(mean) > 1e-9`; and
- full set, half 0, and half 1 all have the same sign.

No source may occur in both halves for the same aggregate pair.

Report the overall direction-stable fraction and the direction-stable fraction
restricted to observed conditional-variation pairs.

The split-half test measures reproducibility inside the observed T092 sample
surface only. It is not held-out normal-information policy evaluation.

## Primary Feasibility Gate

The empirical repeated-public-state aggregation route is considered sufficiently
supported to justify a separate T034 sampler investment only when all of the
following hold on the exact primary `k_min=8` surface:

1. at least `100` distinct repeated public fingerprints contribute;
2. at least `500` distinct fingerprint/action-pair aggregates contribute;
3. at least `70%` of all primary aggregate pairs are direction-stable;
4. at least `100` primary aggregate pairs exhibit observed conditional
   variation; and
5. at least `60%` of those conditional-variation pairs are direction-stable.

These are feasibility thresholds for deciding whether the observed aggregation
idea has a broad reproducible signal. They do not define a future T034 sampling
budget, training target, policy gate, or deployment criterion.

The complete `k_min={2,4,8,16}` support/stability sensitivity table is required
context; the primary decision must not be moved to another `k_min` after
results are known.

## Terminal Classifications

Exactly one terminal classification must be recorded.

### `EMPIRICAL_PUBLIC_AGGREGATION_FEASIBLE`

All artifact/information predicates and all five primary feasibility predicates
pass.

Interpretation:

> Existing T092 repeated-public-state observations contain a broad, reproducible
> empirical aggregate action-preference signal even though individual
> Oracle-conditioned observations may disagree.

Consequence:

Planner may prioritize a separately published native
public-consistent-hidden-future sampler / T034 capability task. T095 itself does
not authorize native modification, model training, or belief-search
implementation.

### `EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE`

Artifacts are valid, but predicates 1, 2, or 4 fail.

Interpretation:

> The current retained repeated-public-state surface does not contain enough
> distinct-source repeated observations to validate the aggregation idea at the
> preregistered scale.

Consequence:

Do not infer that hidden-future averaging is scientifically wrong. Planner must
decide whether a new data-generation/sampler feasibility effort is justified
without empirical support from T092.

### `EMPIRICAL_PUBLIC_AGGREGATION_NOT_STABLE`

Scale predicates 1, 2, and 4 pass, but direction-stability predicate 3 or 5
fails.

Interpretation:

> Repeated public states are sufficiently numerous, but the current
> Oracle-conditioned aggregate preference is not reproducible enough on the
> observed T092 surface to serve as evidence for a simple averaging target.

Consequence:

Do not train a student from these aggregates. A successor may investigate
sampling bias, richer public history/state representation, continuation
information leakage, or a more principled T034 belief-state design.

### `INCOMPLETE`

Any required accepted artifact, lineage fact, public-information boundary, or
deterministic aggregation fact is missing, invalid, or conflicting.

## Required Report

Retain one compact report with:

- exact input identities and hashes;
- exact 413-start source inventory;
- repeated fingerprint/action-pair support counts for `k_min=2/4/8/16`;
- source-group support composition;
- primary aggregate distribution summaries;
- observed conditional-variation counts;
- split-half direction-stability counts/fractions;
- at least bounded quantile summaries of source counts and aggregate deltas;
- exact primary-gate predicate outcomes;
- terminal classification;
- bounded successor recommendation matching the classification;
- artifact SHA-256 and size.

Large per-occurrence data may be streamed and need not be duplicated into a new
corpus if the compact report can be recomputed from the exact retained T092
artifacts.

## Controls Against Over-Interpretation

T095 must not:

- call differing Oracle-conditioned observations label corruption;
- delete a repeated public state merely because teacher preference signs differ;
- use hidden simulator fields as aggregation keys or student-visible content;
- infer a true hidden-future probability from occurrence frequency;
- weight a source start more heavily because Search revisited the same public
  fingerprint more often;
- treat current Oracle continuation as a public-only continuation policy;
- modify Search, Search budget, Search allocation, rollout, backup, or terminal
  utility;
- implement the T034 sampler;
- perform Battle replay or simulator execution;
- train or select a student checkpoint;
- integrate a student into Search;
- evaluate complete A20 runs;
- modify Non-Combat learning; or
- authorize T066.

The existing project objective of eventual A20 Heart success and future
continuation-value learning remains unchanged and outside T095.

## Deliverables

Before final acceptance the PR must contain or durably reference:

- one versioned offline aggregation implementation;
- focused tests for source-macro weighting, sign retention, deterministic
  split-half assignment, public-information firewall, and fail-closed lineage;
- one compact scientific report/retention manifest;
- exactly one terminal classification;
- factual `docs/current_status.md` and task-index terminal updates.

No checkpoint, new simulator artifact, new Search corpus, or native build is
required.

## Execution Authority

No implementation or scientific execution begins before Maintainer exact-head
approval:

```text
SPEC APPROVED

task: T095
approved_spec_commit: <full SHA containing this contract>
implementation_authorized: true
```

Ordinary streaming/storage/report-schema/CLI/helper/process details are
Maintainer/Implementer execution choices unless they change the scientific
meaning above.

A material change to the accepted T092 input identity, public fingerprint,
`n_min=4` support rule, source-start macro weighting, `k_min` set, split-half
definition, feasibility thresholds, terminal classification, or successor
meaning requires Planner amendment and renewed Maintainer exact-head approval.

## Acceptance Criteria

T095 is acceptable only if it:

- is purely offline over exact retained accepted artifacts;
- preserves all observed sign disagreement rather than deleting it;
- uses source-start macro cells as the primary aggregation unit;
- reports the full registered support/stability sensitivity surface;
- makes no claim of posterior-correct hidden-future expectation or
  normal-information optimality;
- performs no model training, Search/simulator execution, native change, or
  controller integration;
- leaves T034 unresolved except as a possible separately published successor;
- leaves Battle-to-run continuation-value learning separate; and
- leaves T066 unauthorized.
