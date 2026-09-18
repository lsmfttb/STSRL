# T093: Internal-State Partial-Ranking Public Battle-Student Distillation Gate

Artifact Eligibility Required: true

## Objective

Test whether a public-information Battle student can learn a generalizable,
state-dependent action-preference rule from the accepted T092 depth>=1 internal
Search-v2@400 partial-ranking surface.

T093 asks one bounded question:

> On the exact retained T092 internal teacher-data surface, does one fixed
> public-only action-conditioned student trained from the preregistered
> `n_min=4` partial rankings outperform both a label-destruction control and a
> state-ablated action-only control on leakage-safe held-out Battle starts?

This is a Battle-student **local distillation / learnability gate**. The teacher
remains frozen and privileged. T093 does not integrate the student into Search,
modify Search, run complete A20 promotion, or establish Battle-policy
improvement.

A positive result supports at most:

> A public-only Battle student can learn a generalizable action-preference
> signal from frozen Search-v2@400 internal partial-ranking self-generated
> supervision on the held-out T087/T090 distribution.

It does not establish that the student improves Battle outcomes, improves
Search, improves complete runs, matches a normal-information-optimal teacher, or
is deployable.

## Current Main Baseline

Planner publication base:

`main @ f7b1512363787d28cc2ba3cb79c7292ab797c6ba`

Accepted T092 scientific lineage:

- final PR head:
  `47ac884b32f88e72d7468bbf643c50bdf4c80fcd`;
- validated implementation/evidence head:
  `1e3dff2665d38dfd6acc786666c1889bc8327508`;
- approved T092 scientific contract:
  `955a095e1e881aa91535dd0d5ed4671cdc44964f`;
- task-native telemetry commit:
  `a439c70b568eab78dea42fe857dab56fa27cda3f`;
- publication native base:
  `20a6c2b3a9cea817c988178b814f083ff889853f`;
- formal evidence SHA-256:
  `ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a`;
- retention manifest SHA-256:
  `32f4b04f31c91cf58928503d51023ba53c98f310bcb96644503040b2fd9d18b7`.

T092 completed the exact T087/T090 413-start cohort, reproduced 6,369 frozen
Search decisions, retained 1,656,822 depth>=1 internal occurrences, and passed
its preregistered `n_min=4` density/diversity gate. Its terminal classification
is `INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH`.

The accepted research sequence is:

- T090: complete-root-Q extraction was too sparse and is closed as the learner
  interface;
- T091: root-level partial-ranking supervision was materially denser but still
  `ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED`;
- T092: stable depth>=1 internal public decision states provide a materially
  larger valid self-generated partial-ranking surface.

T034 remains blocked and its privileged-teacher / information-set ambiguity
warning remains active. T089 did not establish a learned Non-Combat update
operator. T066 remains DRAFT and unauthorized.

## Dependencies

Required accepted dependencies:

- T011: public tactical Battle-state feature contract;
- T016: public-context provenance and audit boundary;
- T025/T062: Search telemetry and frozen Search-v2 controller semantics;
- T078: restore/public/legal-action fidelity;
- T081: scientific artifact eligibility contract;
- T087/T088: exact matched Battle-start cohort and frozen Search-v2@400
  non-learned Battle baseline;
- T090/T091: failed complete-root and root-partial learner-interface evidence;
- T092: accepted internal-state teacher-data surface and retained evidence.

## Inputs And Artifacts

T093 consumes the exact retained T092 formal scientific-quality corpus and
manifest. It must not silently recollect a new teacher dataset or substitute a
different Search run.

The retained T092 artifact root recorded on current `main` is:

`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-formal-413-1e3dff2-20260918/`

Scientific materialization must bind the accepted T092 evidence and retention
hashes above, the exact inherited T090/T092 split assignments, the public
fingerprint contract, the frozen `n_min=4` support definition, and the exact
teacher-searchable/public-excluded action boundary.

If the retained corpus needed to materialize the T093 examples is unavailable,
incompatible, or cannot be tied back to the accepted T092 manifest and
provenance, T093 is `INCOMPLETE`. Re-running Search to recreate an approximately
equivalent corpus is not authorized by this task.

Large derived datasets and checkpoints remain outside Git. The PR must retain
enough exact identities, hashes, configuration and lineage to reproduce or
safely reuse the scientific result.

## Artifact Eligibility Contract

Reuse mode: `scientific_quality_claim`.

The exact T092 retained corpus is eligible only if all of the following remain
true:

- source starts, source groups and inherited train/validation/held-out ownership
  are exactly the accepted T087/T090/T092 identities;
- every learning-eligible example is a stable T092 `tree_depth >= 1` public
  decision state;
- the primary surface is exactly T092 `n_min=4`;
- supported teacher-searchable actions have the accepted finite teacher means
  and visit support; teacher-excluded or unsupported actions are never assigned
  invented targets;
- the T092 public fingerprint, cross-split exclusion and within-split canonical
  deduplication rules are reproduced exactly;
- no hidden/private simulator field enters student-visible input;
- required corpus, configuration, checkpoint and evaluation identities are
  explicit and internally consistent.

Missing, conflicting, inferred, regenerated-substitute or unverifiable material
facts fail closed to `INCOMPLETE`.

## Scientific Dataset

### Primary supervision surface

Use only the accepted T092 `n_min=4` depth>=1 partial-ranking surface.

For one canonical public fingerprint, let `A_s` be the teacher-searchable
actions with child visits >=4 and finite teacher means. For every unordered pair
in `A_s`:

- if the teacher means differ by at most `1e-9`, record a tie diagnostic and do
  not create a ranking pair;
- otherwise the larger teacher mean defines the preferred action.

No preference is created against an unsupported or teacher-excluded action.
Teacher mean magnitude is not a regression target in the primary objective.

The T092 sensitivity surfaces at `n_min={1,2,8,16}` may be reported as
descriptive diagnostics only. They must not replace `n_min=4` as the training or
promotion surface after results are observed.

### Leakage-safe split

T093 inherits the exact T090/T092 source-start split: every internal occurrence
from one Battle start remains owned by that start's train, validation or
held-out split.

The T092 public fingerprint boundary remains authoritative:

- a fingerprint occurring in more than one split is excluded from all learning
  and formal evaluation;
- within one split, one deterministic canonical occurrence per fingerprint is
  retained for the primary dataset;
- split ownership is never reassigned after teacher statistics are observed.

Held-out data must not select architecture, optimization settings, epoch,
checkpoint, seed, target construction, threshold or control.

### Effective-diversity admission

Before training, the exact materialized `n_min=4` corpus must satisfy all of:

- at least 10,000 canonical pair-bearing train fingerprints;
- at least 2,000 canonical pair-bearing validation fingerprints;
- at least 3,000 canonical pair-bearing held-out fingerprints;
- in every `(split, source-group A/B/C)` cell, at least 75% of inherited source
  starts contribute at least one canonical pair-bearing fingerprint;
- every retained pair and fingerprint has exact source-start ownership needed
  for source-start-macro evaluation.

If these predicates fail while the corpus is otherwise valid, terminate as
`INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT`. This is a statement
about the effective learning/evaluation surface after leakage handling, not a
reversal of T092's accepted aggregate density result.

## Public-Only Student

The student is one fixed action-conditioned scorer:

```text
f_theta(public_battle_state, public_action_identity_and_parameters) -> scalar
```

For scientific comparability, use the same bounded feed-forward capacity family
that T090 preregistered, while replacing T090's complete-root-Q interface with
the T092 partial-ranking surface:

- deterministic accepted public state/action encoding;
- concatenated state/action input;
- two hidden layers of width 256 with ReLU;
- one scalar action score;
- no recurrent state, attention, tree input, Search statistic or hidden
  simulator field.

This architecture is a controlled-capacity diagnostic, not a claim that it is
the best Battle model. No architecture or feature sweep is allowed in T093.

Forbidden student inputs include source identity, split, tree depth/path,
occurrence identity, Search visits/means/counters, terminal outcome, checkpoint
or RNG state, hidden draw order, unrevealed future information, and any other
private simulator state.

## Training Objective

For each canonical fingerprint, use pairwise logistic ranking loss over the
non-tied `n_min=4` teacher preference pairs.

To prevent one high-branching state or one long Battle from dominating merely
because it contributes more pairs or internal nodes, the formal objective is
macro-weighted:

1. average pair loss within each canonical fingerprint;
2. average fingerprint losses within each source Battle start;
3. average source-start losses within the split.

Equivalent implementations of this weighting are allowed.

Do not weight the primary loss by Search visits, teacher-mean magnitude, tree
depth, source group, occurrence multiplicity or terminal Battle outcome.

Formal optimization is fixed:

- AdamW;
- learning rate `1e-3`;
- weight decay `1e-4`;
- maximum 30 epochs;
- three initialization seeds: `930093`, `930094`, `930095`;
- for each seed/arm, select one checkpoint using validation macro ranking loss
  only;
- no hyperparameter sweep and no held-out selection.

Batch layout, gradient accumulation, checkpoint serialization, module names and
ordinary training-process mechanics are implementation freedom provided the
frozen objective and effective optimization are preserved.

## Controls

T093 has two required learned controls plus the analytical 0.5 chance reference.

### Label-destruction control

Train the same public-state/action architecture under the same optimization and
three initialization seeds, but destroy the action-to-teacher association on
train and validation data.

For each canonical fingerprint with `k >= 2` supported actions, deterministically
apply a non-zero cyclic shift of the teacher target assignment across those
supported actions, with the shift derived from a fixed task domain separator
`T093-LABEL-DESTRUCTION-V1` and the public fingerprint.

This preserves the state, supported action set, target-value multiset, pair
count, branching structure and source distribution while breaking the true
teacher action preference. Held-out labels are never destroyed and are always
the true frozen teacher labels for evaluation.

### State-ablated action-only control

Train on the true `n_min=4` targets with the same architecture, optimizer,
schedule and seeds, but replace the public Battle-state input by one fixed
constant while retaining the public action identity/parameters.

This control measures how much apparent performance can be explained by global
action priors or action-encoding artifacts without a state-dependent public
decision rule.

The true student must outperform both learned controls. A random/chance pairwise
reference of 0.5 is reported but is not a substitute for either control.

## Evaluation

### Statistical unit

Internal fingerprints from one restored Battle start are correlated. Formal
held-out inference therefore uses the **Battle start**, not the individual pair,
as the independent resampling unit.

For each model seed:

1. compute pairwise ranking accuracy within each canonical fingerprint;
2. macro-average fingerprints within each source Battle start;
3. report source-start values and the mean across held-out starts.

The primary arm statistic averages the three seed-specific source-start values.
Seed-specific results remain separately reported.

### Primary held-out gate

Use a stratified paired bootstrap over held-out source Battle starts, preserving
source-group A/B/C strata:

- 20,000 replicates;
- seed `930293`;
- two-sided 95% percentile intervals.

The primary metric is source-start-macro pairwise ranking accuracy on true
held-out `n_min=4` teacher preferences.

`INTERNAL_STATE_BATTLE_STUDENT_SIGNAL_ESTABLISHED` requires all validity and
effective-diversity predicates plus all of:

1. the true student's 95% CI lower bound is strictly greater than 0.5;
2. the 95% CI lower bound for
   `(true student - label-destruction control)` is strictly greater than 0;
3. the 95% CI lower bound for
   `(true student - state-ablated action-only control)` is strictly greater than
   0;
4. for at least two of the three matched initialization seeds, the true
   student's held-out point estimate is >0.5 and strictly exceeds both matched
   controls;
5. the information, leakage and provenance boundaries have zero violations.

This gate tests a state-dependent learned preference signal. It does not compare
Battle wins and does not promote the student as a controller.

### Required secondary reporting

Report, without creating extra promotion gates:

- train, validation and held-out pairwise ranking accuracy for every seed/arm;
- learning curves and selected epoch for every seed/arm;
- supported-action top-set agreement;
- teacher regret among supported `n_min=4` actions;
- source-group A/B/C breakdown;
- depth and supported-branching breakdown;
- teacher-searchable action-kind breakdown;
- teacher preference-margin breakdown;
- per-start example concentration and multiplicity;
- seed-to-seed variation;
- the analytical 0.5 pairwise chance reference.

Secondary metrics do not override the primary held-out gate.

## Repeated-Public-State / Privileged-Teacher Ambiguity

T034's information-set warning remains in force. The T092 teacher is
`full_simulator_state_oracle_like`; one public state can correspond to multiple
hidden realizations with different privileged preferences.

Use the pre-dedup T092 repeated-fingerprint evidence only for diagnosis. For the
primary `n_min=4` surface, report at least:

- fraction of canonical fingerprints with repeated occurrences;
- selected/best-supported action disagreement where defined;
- fraction of repeated fingerprints for which the same supported public action
  pair is observed with both preference signs;
- pair-sign conflict rate and support counts;
- true-student and control performance separately on fingerprints with observed
  pair-sign conflict and on singleton/no-observed-conflict fingerprints.

No conflict flag, multiplicity, hidden realization identity or teacher
disagreement statistic may enter the primary student input or reweight the
primary training objective.

A low observed conflict rate does not establish normal-information teacher
validity; these are lower-bound diagnostics only.

A failed overall held-out gate may be classified
`INTERNAL_STATE_STUDENT_REPEATED_PUBLIC_CONFLICT_LIMITING` only when all of the
following diagnostic conditions hold:

- the model/optimization fit sanity check below passes;
- both the conflict-bearing and singleton/no-observed-conflict held-out strata
  contain at least 500 canonical fingerprints from at least 15 held-out source
  starts;
- on the singleton/no-observed-conflict stratum, the true student passes the
  same chance and both-control directional comparisons as the primary gate;
- the paired source-start bootstrap lower bound for the difference in
  true-student advantage
  `(no-observed-conflict minus conflict-bearing)` is strictly greater than 0.

This classification means observed repeated-public-state teacher conflict is
consistent with limiting public distillation. It does not prove that privileged
teacher ambiguity is the sole cause or solve T034.

## Failure Diagnosis And Terminal Classifications

Exactly one terminal classification must be recorded, using this precedence
after provenance/information validation.

### `INTERNAL_STATE_BATTLE_STUDENT_SIGNAL_ESTABLISHED`

The effective-diversity and primary held-out gates pass.

Consequence: Planner may consider one separate Search-integration experiment.
T093 itself does not authorize Search integration.

### `INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT`

The exact T092 corpus is valid, but the frozen post-leakage T093
effective-diversity admission fails.

Consequence: do not infer that Battle learning is impossible. Diagnose which
split/source-start or pair-structure bottleneck remains before changing the
teacher-data generator.

### `INTERNAL_STATE_STUDENT_MODEL_OR_OPTIMIZATION_INADEQUATE`

The dataset is valid and sufficiently diverse, but the true-label student cannot
fit the training supervision: fewer than two of the three seeds reach
source-start-macro training pairwise accuracy of `0.70`.

Consequence: the current fixed model/optimization capacity is not an adequate
test of whether the supervision can generalize. Do not interpret the result as
absence of learnable Battle signal.

### `INTERNAL_STATE_STUDENT_REPEATED_PUBLIC_CONFLICT_LIMITING`

The overall primary held-out gate fails, model fit is adequate, and the
preregistered repeated-public-state conflict diagnostic above passes.

Consequence: the result is consistent with T034-style privileged-teacher
ambiguity materially limiting the public student on this surface. A successor
must address the information-set/target issue rather than merely tuning the same
student.

### `INTERNAL_STATE_STUDENT_GENERALIZATION_NOT_ESTABLISHED`

The dataset is valid, model fit is adequate, and the overall primary held-out
gate fails without satisfying the conflict-limiting diagnosis.

Consequence: the chosen public representation/model/partial-ranking target did
not establish a generalizable held-out signal. Report whether the failure is
concentrated by source group, depth, branching, action kind or teacher margin.
Do not conclude that Battle learning is impossible and do not repeatedly tune
the same task without a new mechanism-level hypothesis.

### `INTERNAL_STATE_STUDENT_INFORMATION_BOUNDARY_INVALID`

Hidden/private information entered student-visible inputs, split leakage was
not removed under the frozen fingerprint rule, or required public/teacher action
boundaries cannot be established.

### `INCOMPLETE`

Required retained corpus, provenance, model/control training, held-out report or
other mandatory scientific evidence is missing or invalid.

## Scope

T093 may implement only the minimum offline materialization, fixed training and
evaluation capability needed to run this contract on the accepted T092 data.

T093 must not:

- modify Search-v2@400, its native telemetry, action selection, allocation,
  rollout, backup, terminal utility or action space;
- enable potions or force Search exploration to create labels;
- recollect the T092 teacher corpus as an ordinary execution choice;
- integrate the student into Search at any location;
- run fresh complete A20 natural-run promotion or Heart evaluation;
- claim standalone Battle-controller superiority;
- use human trajectories, human actions, card/deck rankings or handcrafted
  strategy imitation;
- use CombatSolver labels, heuristics or trajectories;
- train or modify Non-Combat policy;
- authorize T066;
- run an architecture, feature, target-threshold or hyperparameter sweep.

Ordinary module layout, APIs, schema mechanics, runner/CLI shape, process
topology, logging, temporary files, helper structure and resource orchestration
remain Maintainer/Implementer execution choices unless they create a material
scientific difference.

## Deliverables

Before final acceptance, the task PR must contain or durably reference:

- exact T092 input/retention identities and materialization provenance;
- leakage-safe split/fingerprint and effective-diversity report;
- frozen student/control scientific configuration;
- all three seeds of true-student, label-destruction and state-ablated training
  summaries and selected checkpoint identities;
- complete held-out source-start-macro primary statistics and bootstrap report;
- required repeated-public-state conflict diagnostics;
- required secondary stratified diagnostics;
- scientific-quality retention manifest for large external artifacts;
- factual terminal classification and bounded interpretation;
- final Task Index lifecycle/result update;
- factual `docs/current_status.md` result update before dual final acceptance
  whenever practical.

Maintainer final implementation/operational acceptance and Planner final
scientific/architecture acceptance must reference the same exact final PR head.

## Execution Authority

No implementation or scientific execution may begin before Maintainer exact-head
approval of this task contract:

```text
SPEC APPROVED

task: T093
approved_spec_commit: <full SHA containing this contract>
implementation_authorized: true
```

After approval, ordinary implementation design, training execution readiness,
runtime/resource evidence, retries that do not change scientific meaning, and
other execution coordination belong to Maintainer/Implementer under
`docs/collaboration_workflow.md`.

A material change to the source corpus, public-information boundary, split or
fingerprint rule, `n_min=4` primary surface, controls, model/training scientific
configuration, primary evaluation statistic, success predicates, terminal
meaning or successor boundary requires a Planner amendment and renewed
Maintainer exact-spec approval.

## Acceptance Criteria

T093 is acceptable only if:

- it consumes the exact accepted T092 scientific-quality lineage or fails closed;
- it preserves the public-only student boundary and inherited leakage-safe split;
- it uses the frozen `n_min=4` internal partial-ranking target without inventing
  unsupported action labels;
- the true student and both required controls are scientifically matched except
  for their registered signal destruction/ablation;
- formal inference is source-start clustered and held-out data are untouched by
  model selection;
- the exact terminal classification follows the preregistered logic;
- the final interpretation stays within the task's bounded claim;
- no Search integration, complete-run promotion, Non-Combat update or T066 work
  enters the task.

## Successor Boundary

Even after `INTERNAL_STATE_BATTLE_STUDENT_SIGNAL_ESTABLISHED`, the next
scientific question is separate:

> Does using the accepted public-only student at one explicitly defined Search
> integration point improve frozen Search on a matched Battle cohort under
> controlled compute and the normal public student information boundary?

That successor must independently preregister its Search integration mechanism,
matched comparator, cost accounting, cohort and promotion gate. T093 does not
authorize it automatically and must not implement it in the same PR.

If T093 fails, successor reasoning must follow the observed failure class:

- effective-diversity failure -> diagnose data/pair/source-start structure;
- model/optimization inadequacy -> revise the bounded learner test rather than
  reject Battle learning;
- repeated-public-state conflict limitation -> address information-set/target
  ambiguity;
- otherwise no held-out generalization -> formulate a new mechanism-level
  representation/target hypothesis before another training task.

T066 remains unauthorized until Battle and Non-Combat each have a credible
learned update operator beyond local diagnostic fit.
