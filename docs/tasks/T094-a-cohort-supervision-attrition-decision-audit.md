# T094: A-Cohort Supervision Attrition Decision Audit

Artifact Eligibility Required: true

## Objective

Determine, with the smallest useful offline audit, why T093's frozen source-start
effective-diversity gate failed specifically on source group A and which
scientific successor is justified.

T094 asks only this decision question:

> Did source group A lose the T093 75% independent-start coverage target before
> meaningful Search action support existed, specifically when raising support to
> `n_min=4`, or mainly during leakage-safe fingerprint
> exclusion/canonicalization?

The answer is used only to choose among three successor directions:

1. treat A as a low-supervision hard/stress distribution under frozen
   Search-v2@400 and reconsider whether A should be a mandatory training-source
   coverage population;
2. investigate Search/teacher support quality or an alternative future
   supervision-generation mechanism;
3. repair the leakage-safe dataset construction if valid supervision exists but
   canonicalization removes the required independent-start coverage.

T094 does not train a student, modify Search, rerun Battle simulation, change
T093 thresholds after the fact, or establish that any future student will learn.

## Current Accepted Baseline

Publication base:

`main @ dd45aef9c5f1299e85297ccf185562891c2aa080`

Accepted T092 lineage:

- formal implementation/evidence head:
  `1e3dff2665d38dfd6acc786666c1889bc8327508`;
- formal evidence SHA-256:
  `ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a`;
- retention manifest SHA-256:
  `32f4b04f31c91cf58928503d51023ba53c98f310bcb96644503040b2fd9d18b7`;
- exact retained artifact root:
  `/mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-formal-413-1e3dff2-20260918/`.

Accepted T093 lineage:

- final PR head:
  `b864bfe79ba225c9a4ebc80622a0f5dcc740f9c2`;
- merge commit:
  `dd45aef9c5f1299e85297ccf185562891c2aa080`;
- derived corpus SHA-256:
  `c6ea76b149b54502eed1da0741914b80ca13cdd84cad5e518eae410399c90ca9`;
- T093 retention-manifest SHA-256:
  `5c42482003611878a0c56108fea0a3c8f8a287e6ec7ab1d1f8817bd741fb71b6`;
- retained artifact root:
  `/mnt/d/DeadlyCatCoding/STSRL/artifacts/t093-internal-state-student-66fe372-20260918/`;
- terminal classification:
  `INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT`.

T093's accepted final canonical corpus contains train/validation/heldout
`25,825 / 5,842 / 8,383` pair-bearing fingerprints. Final contributing
source starts by A/B/C are:

- train: `30 / 119 / 77`;
- validation: `6 / 30 / 20`;
- heldout: `9 / 43 / 27`.

The exact inherited source-group sizes are A/B/C = `93 / 192 / 128`. Group A
is the retained T052 hard/stress Boss/later-act cohort; B is the T085 selected
mixed cohort; C is the T085 current-policy occupancy cohort.

## Artifact Eligibility Contract

### Inputs

Use only the exact accepted T092 retained formal source records/evidence and the
exact accepted T093 derived corpus/retention identities above.

No new Search run, Battle replay, source recollection, replacement cohort,
reseed, regenerated substitute, or approximate artifact is eligible.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T094 may claim only where independent source-start coverage is lost along the
already accepted T092 -> T093 supervision pipeline and which preregistered
successor category that observed attrition supports.

T094 does not establish student learnability, teacher correctness, Battle-policy
improvement, Search improvement, complete-run improvement, normal-information
optimality, or deployment readiness. It does not retroactively alter T092 or
T093.

### Required predicates

- exact T092/T093 artifact hashes and source identities validate;
- all 413 source starts preserve their accepted A/B/C group and inherited
  train/validation/heldout ownership;
- candidate occurrences use the accepted T092 stable depth>=1 public-state
  boundary and teacher-searchable action boundary;
- support thresholds are exactly `n_min={1,2,4}` for this audit;
- pair-bearing means at least one non-tie unordered supported-action comparison
  under the accepted `1e-9` tie tolerance;
- the `n_min=4` leakage and canonicalization stages reproduce T093 exactly;
- no hidden/private field changes eligibility except existing accepted teacher
  support metadata;
- all reporting remains source-start based; raw occurrence counts may not stand
  in for independent-start coverage.

### Unavailable-fact behavior

Missing, conflicting, inferred, filename-derived, regenerated-substitute, or
unverifiable material facts fail closed to `INCOMPLETE`.

## Minimal Audit

For every source start, compute only the following stage indicators.

### Stage S1: pre-dedup pair-bearing support

Using the exact T092 retained depth>=1 stable internal occurrences, before any
cross-split fingerprint exclusion or within-split canonical deduplication,
record whether the start contains at least one public fingerprint with at least
one non-tie pair at each of:

- `n_min=1`;
- `n_min=2`;
- `n_min=4`.

Do not change the teacher action space, tie tolerance, or public projection.

### Stage S2: n_min=4 after cross-split exclusion

Apply the exact T092/T093 public fingerprint and inherited split rule. If one
fingerprint appears in more than one split, exclude all occurrences of that
fingerprint.

Before within-split canonical ownership/deduplication, record whether each
source start still owns at least one remaining `n_min=4` pair-bearing
fingerprint occurrence.

### Stage S3: exact final T093 canonical corpus

Apply the exact accepted within-split deterministic canonical occurrence rule
and record final source-start contribution.

S3 must reproduce the accepted T093 final counts exactly before T094 may draw a
scientific conclusion.

## Required Report

For A/B/C separately and for train/validation/heldout plus all splits combined,
report:

- exact source-start denominator;
- contributing-start count and fraction at S1 for `n_min=1,2,4`;
- contributing-start count and fraction at S2;
- contributing-start count and fraction at S3;
- absolute and fractional start loss from S1(`n_min=1`) -> S1(`n_min=2`)
  -> S1(`n_min=4`) -> S2 -> S3.

For final S3 only, also report a lightweight concentration summary per source
group:

- median canonical pair-bearing fingerprints per contributing start;
- 90th percentile;
- maximum;
- fraction of group examples contributed by the top 10% of contributing starts.

These concentration statistics are descriptive only and do not create another
gate.

No per-encounter, per-card, per-action-kind, deck archetype, or detailed Battle
forensic analysis is required by T094.

## Exact Reproduction Gate

Before route interpretation:

1. the source ledger must reproduce A/B/C = `93/192/128`;
2. S3 train/validation/heldout canonical fingerprint counts must reproduce
   `25,825/5,842/8,383`;
3. S3 contributing starts must reproduce exactly:
   - train A/B/C = `30/119/77`;
   - validation A/B/C = `6/30/20`;
   - heldout A/B/C = `9/43/27`.

Any mismatch is `INCOMPLETE`; T094 must not explain the T093 result from a
non-equivalent pipeline.

## Decision Classification

Exactly one terminal classification is recorded after the reproduction gate.

The original T093 75% start-coverage criterion is used here only as a diagnostic
reference for deciding where that already-frozen criterion became unattainable.
T094 does not amend T093.

Let A-wide coverage use all 93 accepted A starts.

### `A_COHORT_LOW_SUPERVISION_BEFORE_SUPPORT_THRESHOLD`

Use when fewer than `ceil(0.75 * 93) = 70` A starts are pair-bearing already
at pre-dedup `n_min=1`.

Interpretation:

> Under frozen Search-v2@400, broad independent-start pair supervision is absent
> on the hard/stress A cohort even at the weakest observed-visit support
> threshold. The T093 75% A-training-source coverage assumption is therefore not
> realistic for this teacher/data surface.

Successor direction: do not tune the T093 learner or simply lower its threshold.
Planner should consider a research design in which B/C-like supervision is the
learnability/training population and A is reserved for a separately specified
hard/stress transfer or downstream Battle evaluation, unless a new
data-generation mechanism is independently motivated.

### `A_COHORT_VISIT_SUPPORT_LIMITING`

Use when at least 70 A starts are pair-bearing at pre-dedup `n_min=1`, but
fewer than 70 remain pair-bearing at pre-dedup `n_min=4`.

Interpretation:

> Most A starts expose some action comparison, but the frozen Search@400 visit
> allocation does not support those comparisons broadly enough at the accepted
> `n_min=4` confidence surface.

Successor direction: a separate task may test supervision reliability across
support thresholds or motivate a different teacher/data-generation mechanism.
T094 does not authorize retroactively training T093 at `n_min=1` or `2`.

### `A_COHORT_CANONICALIZATION_LIMITING`

Use when at least 70 A starts are pair-bearing at pre-dedup `n_min=4`, but
fewer than 70 contribute to final S3 after leakage-safe exclusion and
canonicalization.

Interpretation:

> Frozen Search supplies broad A-start `n_min=4` supervision, but the current
> leakage-safe dataset construction removes enough independent-start ownership
> to make the T093 training population inadmissible.

Successor direction: inspect and redesign the split/fingerprint/canonical
ownership construction while preserving the public-information and leakage
firewalls before another learnability experiment.

### `INCOMPLETE`

Required accepted artifacts or material facts are unavailable or invalid, or
the accepted T093 S3 result cannot be reproduced exactly under its published
rules. No successor interpretation is allowed from a non-equivalent pipeline.

## Controls Against Over-Interpretation

B and C are mandatory same-pipeline controls. They determine whether an observed
drop is A-specific or a general property of the support/canonicalization stage.

T094 must not:

- infer causality from Battle difficulty alone;
- claim that fast death, branching factor, Battle length, or a particular game
  mechanic caused attrition unless already explicit in the minimal stage counts;
- run a new simulator diagnostic merely to explain the result;
- lower the 75% diagnostic reference after observing the audit;
- train any model;
- modify Search or its visit allocation;
- create a new learned target;
- integrate a student;
- run complete A20 evaluation;
- modify Non-Combat learning;
- authorize T066.

If the three-stage audit does not distinguish the successor routes, Planner may
decide whether a second mechanism-level audit is worth publishing. T094 itself
must stop rather than expand scope.

## Deliverables

Before final acceptance the PR must contain or durably reference:

- exact T092/T093 input identities;
- one compact source-start stage table or JSON report;
- exact S3 reproduction evidence;
- A/B/C and split-level coverage table;
- the S3 concentration summary;
- exactly one terminal classification;
- a bounded successor recommendation matching that classification;
- factual task-index and `docs/current_status.md` updates.

No new large training dataset or checkpoint is required.

## Execution Authority

No audit implementation or scientific execution begins before Maintainer
exact-head approval:

```text
SPEC APPROVED

task: T094
approved_spec_commit: <full SHA containing this contract>
implementation_authorized: true
```

Ordinary parser/API/report schema/CLI/helper/process details are
Maintainer/Implementer execution choices unless they change the scientific
meaning above.

A material change to accepted inputs, stage definitions, support thresholds,
fingerprint/leakage rules, the 75% diagnostic reference, terminal
classification, or successor meaning requires Planner amendment and renewed
Maintainer exact-head approval.

## Acceptance Criteria

T094 is acceptable only if it:

- is purely offline over exact retained accepted artifacts;
- exactly reproduces T093 S3 before interpretation;
- reports start-level rather than occurrence-level attrition;
- uses B/C as same-pipeline controls;
- stops at the first route-relevant explanation;
- makes no model-training or controller-improvement claim;
- leaves T034 unresolved and T066 unauthorized.
