# T091: Battle Teacher Data-Surface Density Audit

## Objective

Determine whether the accepted frozen Battle teacher/controller, unguided Search v2 @400, already exposes a sufficiently dense and scientifically usable **root-level training-data surface** when supervision is defined as partial Search-supported action comparisons rather than complete all-action Q vectors.

T091 addresses the post-T090 architectural diagnosis:

> Search-v2 is an adaptive controller that should concentrate finite search budget on promising actions. T090's 95% complete-root-Q predicate instead asked the controller to behave like an exhaustive all-action evaluator. Controller efficiency and training-label coverage are distinct objectives and must no longer be conflated.

T091 therefore asks one bounded question:

> On the exact accepted T090 formal 413-start Search-v2@400 evidence, how much trustworthy public-action supervision is available if we retain partial root action support, and is that surface dense and broad enough to justify a separate public Battle-student experiment before building a new offline combat data generator?

This is a **teacher-data-surface diagnostic**. It does not train a student, modify Search, implement a CombatSolver-style searcher, integrate learned guidance, or claim Battle-policy improvement.

## Publication Baseline

Planner publication base:

`main @ ca95317ca0f21d5c07cfa0a9c845a26a66548bb4`

Canonical simulator identity at publication:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 20a6c2b3a9cea817c988178b814f083ff889853f`

Accepted scientific context:

- T087: exact 413-row matched Battle-start cohort with source groups A/B/C = 93/192/128;
- T088: unguided Search v2 @400 is the frozen strongest accepted non-learned Battle baseline on that cohort;
- T089: Non-Combat local learnability signal existed, but complete-run improvement was not established;
- T090: exact 413-start Search-v2@400 formal collection produced 6,210 multi-action decisions, but only 309 decisions (4.9758%) met the preregistered complete-root-utility condition; after leakage/deduplication only 293 eligible examples remained (200/46/47), so training correctly did not run;
- the accepted post-T090 interpretation is that complete root-Q extraction is a poor Search-v2 -> learner interface, not that self-generated Battle supervision is intrinsically scarce;
- T034 public-consistent hidden-future sampling remains BLOCKED;
- root-prior allocation repair and learned Battle leaf-value repair remain closed;
- T066 remains DRAFT and unauthorized.

## Research Boundary

T091 must keep these concepts separate:

```text
Search/controller objective:
    allocate compute to improve the selected action

Teacher-data objective:
    expose enough trustworthy state/action supervision for learning
```

The task must not reinterpret poor complete-Q coverage as poor Search quality.

The T090 95% complete-root-Q rate is retained only as a diagnostic reference. T091 must not lower it and rerun T090.

## Explicit Non-Goals

T091 must not:

- change Search-v2 simulations/root, UCT/allocation, root selection, rollout policy, terminal utility, action semantics, or native transition semantics;
- force uniform exploration or minimum visitation of every root action;
- retrain the T090 student or tune its model/training schedule;
- define a lower replacement complete-Q threshold and call T090 repaired;
- inject learned priors, root-allocation guidance, learned leaf values, or post-search bonuses;
- implement a new Beam/DFS/CombatSolver-style offline combat solver;
- add exact transposition/state-identity work;
- train Non-Combat components;
- run complete A20 natural-run evaluation;
- use human trajectories, human action labels, card/deck rankings, or strategy imitation;
- claim that single-hidden-future privileged labels are normal-information optimal policy targets;
- authorize T066.

CombatSolver is architectural inspiration only: T091 may reason about high-throughput explicit state/action expansion as a future data-generation direction, but may not consume CombatSolver trajectories, heuristics, rankings, weights, or labels.

## Dependencies

Required accepted dependencies:

- T011: `public-tactical-v2` Battle-state feature contract;
- T016: public-context provenance/audit boundary;
- T025/T062: native Search telemetry and Search-v2 controller surface;
- T078: restore/public/legal-action fidelity;
- T081: scientific artifact eligibility contract;
- T087: exact matched Battle-start cohort;
- T088: frozen Search-v2@400 Battle teacher/controller;
- T090: accepted formal Search-v2@400 target-generation evidence and terminal coverage result.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

### Primary input

The primary scientific input is the **exact accepted T090 formal 413-start raw target-generation evidence** that produced the accepted terminal statistics:

- 413/413 frozen T087 Battle starts executed under frozen Search-v2@400;
- 6,210 observed multi-action decisions;
- per-decision ordered legal-action identities;
- Search root rows, including visit counts and finite/non-finite `mean_value` state;
- selected Search action;
- public student-visible state / public decision fingerprint inputs where retained;
- source-group/split/provenance/cost identities required by T090 validation.

T091 implementation must resolve the exact retained artifact path/hash and all upstream identities from the accepted T090 retention/terminal provenance before any formal analysis. Filename inference, regenerated substitute tables, smoke/canary evidence, or a different Search rerun are not acceptable replacements.

If the accepted T090 raw evidence does not retain a required field for a registered metric, that metric is `UNAVAILABLE`; the implementation must not reconstruct or impute it from hidden simulator state.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T091 may claim only the density, support geometry, selection bias, and observable ambiguity lower bounds of candidate root-level Search-v2 teacher surfaces on the exact T090/T087 distribution.

T091 does not claim student learnability, Search improvement, complete-run/Heart improvement, normal-information teacher optimality, or deployment readiness.

### Fail-closed behavior

Missing or conflicting T090 artifact identity, native identity, teacher configuration, source ledger, action mapping, split, public fingerprint schema, or cost provenance fails closed to `INCOMPLETE`.

## Candidate Teacher Data Surfaces

Analyze the same T090 decision population under four nested surfaces. No target may be invented for an unvisited action.

### S0 — complete-root-Q reference

The frozen T090 definition:

- multi-action decision;
- every legal action maps exactly once to a root row;
- every action has `visits > 0`;
- every action has finite `mean_value`.

This is diagnostic only and must reproduce the accepted `309 / 6,210 = 4.9758%` raw result before later analysis proceeds.

### S1 — visited-action support

For each multi-action decision, retain each legal action that:

- maps exactly once to a Search root row;
- has finite `mean_value`;
- has positive visits.

Report supported-action count and supported/legal fraction. Unvisited actions remain explicitly unknown, not negative labels.

### S2 — partial pairwise ranking support

For preregistered per-action minimum-visit thresholds:

`n_min in {1, 2, 4, 8, 16}`

an action is supported when it satisfies S1 and `visits >= n_min`.

For every unordered pair of supported actions `(a_i, a_j)`:

- if `abs(mean_i - mean_j) <= 1e-9`, classify the pair as a teacher tie and do not create an ordered label;
- otherwise the larger Search mean defines one ordered Search-supported pair.

These are **Search-exposed preference labels**, not claims of true action-value ordering.

Primary density threshold for successor selection uses `n_min = 4`. The full threshold curve is required to show sensitivity and must not be used as a post-hoc tuning sweep.

### S3 — chosen-action label support

For every valid multi-action Search decision with an exactly mapped selected legal action, record one privileged teacher chosen-action label.

Chosen-action density is expected to be high, but density alone cannot promote it as normal-information ground truth because the teacher uses one realized hidden simulator future. T091 reports this surface for comparison only.

## Public Fingerprint / Ambiguity Boundary

Where T090 retained the versioned public decision fingerprint, group exact repeated public fingerprints without crossing or changing their original source/split identities.

For repeated public fingerprints report:

- occurrence count;
- number of distinct teacher selected actions;
- selected-action disagreement rate;
- number of pairwise preference sign conflicts for action pairs observed in multiple occurrences;
- source/split distribution.

These measurements are only a **lower bound** on Oracle/public information-set ambiguity. A low observed conflict rate does not establish that hidden-future ambiguity is absent because T034 remains blocked and repeated public states may be rare.

If exact public fingerprints are unavailable in the accepted T090 raw artifact, report this section as `UNAVAILABLE`; do not derive them from privileged checkpoint/RNG data.

## Required Density And Bias Metrics

For the full formal population and separately for source groups A/B/C, report at minimum:

1. total decisions, single-action decisions, and multi-action decisions;
2. legal-action-count distribution: mean, median, p75, p90, p95, max;
3. S0 complete-Q eligible count/fraction;
4. S1 supported-action-count and supported/legal-fraction distributions;
5. for each `n_min in {1,2,4,8,16}`:
   - decisions with at least 2 supported actions;
   - fraction of multi-action decisions with at least 2 supported actions;
   - total supported actions;
   - total ordered non-tie pairs;
   - mean/median/p90 ordered pairs per multi-action decision;
   - supported/legal fraction distribution;
6. S3 chosen-action mapping coverage;
7. all metrics stratified by legal-action-count buckets `2`, `3-4`, `5-8`, `9-16`, `17+` where bucket count permits;
8. action-kind coverage using the current public legal-action taxonomy, including how often each kind appears legally, appears with positive visits, and participates in at least one `n_min=4` ordered pair;
9. source-group A/B/C coverage for each surface;
10. duplicate/public-fingerprint multiplicity where available;
11. Search cost normalization using retained T090 counters:
    - usable S0 roots per 1,000 Search simulations;
    - `n_min=4` pair-supported roots per 1,000 Search simulations;
    - `n_min=4` ordered pairs per 1,000 Search simulations;
    - chosen-action labels per 1,000 Search simulations;
    - same metrics per retained wall-clock second only if formal wall-clock provenance exists.

No unretained cost field may be reconstructed after the fact.

## Selection-Bias Audit

T091 must explicitly test whether complete-Q eligibility selects a narrow subset of Battle decisions.

Compare S0-eligible decisions against all multi-action decisions for:

- legal-action count;
- source group;
- Battle turn / decision depth if retained as public/formal metadata;
- action-kind composition;
- selected-action kind;
- terminal outcome/dense T087 diagnostics only where already retained and valid for distribution description.

Also compare `n_min=4` pair-supported decisions against all multi-action decisions using the same available dimensions.

This is descriptive distribution analysis, not a causal claim and not a new reward definition.

## Root-Level Partial-Supervision Viability Gate

T091 does not require complete-Q coverage to be high.

The root-level partial-ranking surface is classified as sufficiently dense for a separate student experiment only if all of the following hold at `n_min = 4` after exact public-fingerprint cross-split exclusion and within-split canonical deduplication where the retained T090 schema supports that operation:

1. at least `70%` of raw observed multi-action decisions contain at least two supported actions;
2. each source group A/B/C individually has at least `60%` of multi-action decisions with at least two supported actions;
3. at least `3,500` unique decision examples remain with at least one ordered non-tie pair;
4. at least `10,000` ordered non-tie pairs remain overall;
5. median supported/legal action fraction is at least `0.40`;
6. no legal-action-count bucket with at least 100 decisions has pair-supported-root coverage below `30%`;
7. at least `90%` of public action kinds that occur in 50 or more legal-action instances participate in at least one `n_min=4` ordered pair;
8. provenance/information-boundary validation has zero violations.

These thresholds are a **data-surface gate**, not a Search performance target. Search-v2 itself must not be modified to satisfy them.

If exact public fingerprint data are unavailable, gates 1-2 and 4-7 are still computed on raw occurrence-safe decisions, but gate 3 is marked unavailable and the task cannot classify the surface as ready for student training; it must instead end in `ROOT_PARTIAL_SUPERVISION_NEEDS_IDENTITY_REPAIR` or `INCOMPLETE` depending on whether the missing field is an accepted-artifact retention limitation or provenance failure.

## Internal Search-State Feasibility Audit

T091 must include a bounded code/architecture audit answering whether current Search-v2 can expose additional **stable public Battle decision states from inside Search** without changing Search semantics.

The audit must identify:

- which internal nodes correspond to quiescent/stable player-decision states rather than transient ActionQueue execution states;
- whether the accepted public projection and legal-action enumeration can be computed at those nodes;
- whether exact parent/root/source provenance can be attached;
- whether exporting them requires new ActionQueue semantic identity, exact transposition, or other simulator redesign already rejected/deprioritized by T079;
- whether root-action Search means/visits have a valid analogue at those internal states under the existing tree, or whether fresh local search would be required.

This section is **feasibility analysis only**. T091 must not implement internal-state export or a new solver.

Possible audit conclusions:

- `CURRENT_SEARCH_INTERNAL_SURFACE_FEASIBLE`: stable public internal decision states can be exported with bounded telemetry-only work and no Search semantic change;
- `CURRENT_SEARCH_INTERNAL_SURFACE_NOT_FEASIBLE`: useful export would require material simulator/Search semantic redesign;
- `CURRENT_SEARCH_INTERNAL_SURFACE_AMBIGUOUS`: current code/provenance is insufficient for a responsible conclusion.

## Formal Decision Cases

Exactly one primary terminal classification must be recorded.

### `ROOT_PARTIAL_SUPERVISION_DENSE_ENOUGH`

All formal evidence is valid and every root-level partial-supervision viability predicate passes.

Consequence: Planner may publish a separate Battle-student task using the frozen partial-pair target definition. That successor must still handle privileged-teacher information-set ambiguity explicitly and must not integrate the student into Search in the same task.

### `ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED`

Formal evidence is valid but one or more density/bias predicates fail.

Consequence: do not train another root-telemetry student merely by relaxing thresholds. Use the internal-state feasibility conclusion to choose between a bounded internal-search-state export task and a dedicated offline Battle data-generator design/feasibility task.

### `ROOT_PARTIAL_SUPERVISION_NEEDS_IDENTITY_REPAIR`

The accepted T090 evidence is otherwise valid and dense enough on raw occurrences, but a required public fingerprint/identity field was not retained, preventing leakage-safe unique-example qualification.

Consequence: only a narrow retention/identity repair may precede a student task; no Search semantic change is authorized.

### `INCOMPLETE`

Required accepted T090 artifact/provenance/action/cost facts are unavailable or inconsistent in a way that prevents the registered analysis.

The internal-state feasibility conclusion is recorded separately and does not replace the primary terminal classification.

## Successor Decision Matrix

The task's final report must map the terminal result to one next research direction:

```text
ROOT_PARTIAL_SUPERVISION_DENSE_ENOUGH
    -> separate partial-ranking Battle-student gate

ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED
    + CURRENT_SEARCH_INTERNAL_SURFACE_FEASIBLE
    -> bounded internal Search-state telemetry/data-surface task

ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED
    + internal surface NOT_FEASIBLE/AMBIGUOUS
    -> dedicated offline Battle data-generator design/feasibility task
       inspired by explicit state/action expansion, pruning, retention,
       and simulator-only self-generation; no human/CombatSolver labels

ROOT_PARTIAL_SUPERVISION_NEEDS_IDENTITY_REPAIR
    -> narrow public-identity retention repair only
```

Chosen-action labels may be reported as a dense fallback surface but must not be selected solely because they are dense. Any future chosen-action student task must retain the T034 information-set ambiguity warning and may claim only privileged-teacher distillation unless a public-consistent hidden-future mechanism exists.

## Execution Authorization

Default serial one-task/one-PR workflow applies.

No implementation or scientific analysis may begin before Maintainer exact-head approval:

```text
SPEC APPROVED

task: T091
approved_spec_commit: <full SHA containing this contract>
implementation_authorized: true
```

After spec approval:

1. implementation may add offline T090-artifact validators, density/bias analysis, reports, deterministic deduplication, tests, and the bounded static/native-code feasibility audit on the same PR;
2. T091 should use the accepted retained T090 artifact and should not launch fresh simulator collection by default;
3. if a required metric truly cannot be computed from retained T090 evidence, no free fresh Search rerun is authorized; the report must mark it unavailable and follow the registered terminal rules;
4. no model training, new native search mechanism, internal-tree export implementation, or complete-run execution is authorized;
5. material changes to surfaces, visit thresholds, viability predicates, or terminal decision logic require Planner amendment and renewed exact-head approval.

## Required Deliverables Before Final Acceptance

The same PR must contain or durably reference:

- exact accepted T090 input artifact identity and SHA-256 plus upstream source/native/teacher provenance;
- validator proving S0 reproduces the accepted 309/6,210 complete-Q result exactly;
- deterministic density report for S0/S1/S2/S3;
- `n_min={1,2,4,8,16}` sensitivity table;
- source-group, branching-factor, and action-kind coverage reports;
- cost-normalized usable-supervision report;
- selection-bias report;
- public-fingerprint disagreement/ambiguity lower-bound report where data exist;
- current Search internal-state feasibility audit with code anchors;
- factual terminal classification and successor decision matrix outcome;
- retained-artifact manifest for any scientific-quality outputs outside Git;
- final task-index lifecycle/result update;
- `docs/current_status.md` factual result update before dual final acceptance whenever practical.

Maintainer final implementation/operational acceptance and Planner final scientific/architecture acceptance must refer to the same exact final PR head before landing.

## Scientific Interpretation Boundary

A positive T091 result means only:

> Existing frozen Search-v2@400 root telemetry contains substantially denser partial Search-supported preference supervision than T090's complete-Q interface retained.

It does not mean the labels are unbiased action values, that a public student can learn them, that the student would improve Search, or that privileged one-hidden-future supervision is normal-information optimal.

A negative T091 result means only:

> Existing root telemetry remains an inefficient or biased training-data surface under the preregistered partial-support definition.

It would justify moving the data-generation problem closer to explicit training-oriented state/action expansion or other dedicated offline teacher machinery rather than further weakening root-coverage gates.