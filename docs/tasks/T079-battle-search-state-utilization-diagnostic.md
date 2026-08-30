# T079: Battle Search Path-Tree State-Utilization Diagnostic

## Objective

Test the specific representation-bottleneck hypothesis raised by T070: the
current Search v2 path tree may spend a material fraction of additional search
budget expanding path-distinct nodes that represent the same future-combat
state.

T079 is a falsifiable measurement task. It adds read-only exact-state utilization
telemetry and reruns only the frozen T070 high-budget `prior_value` diagnostic
family needed to measure that hypothesis. It does **not** implement state
transposition, change search allocation, retrain a model, add Beam search, or
change any controller promotion decision.

## Current Main Baseline

T078 is complete after PR #82 and removed the restored-state fidelity blocker.
The exact retained 320-state restore-only audit passed with `mismatch_count=0`,
no replacement, and no counterfactual continuation execution. The current
accepted native integration remains:

```text
cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083
```

T070 previously ran an outcome-blind 16-record high-budget subset at budgets
100, 400, and 1600. On that subset:

- baseline wins were `2 / 3 / 3`;
- `prior_value` wins were `2 / 2 / 2`;
- `prior_value` selected root actions changed on `8/16` records from budget 100
  to 1600;
- root visit leaders changed on `6/16` records;
- first-root median maximum expanded depth increased from `4` to `8`;
- `budget_100_not_sufficient=true`;
- `high_budget_guidance_signal=false`.

T070 measured path-tree nodes and edges, but explicitly did not require hidden
state hashes or transposition hashes. It therefore did not answer how many
**distinct future-combat states** those additional path nodes represented.

T079 answers only that missing question.

## Dependencies

T078, T070, T069, T062, T052, T043, T017, and T020.

## Frozen Inputs

Use the exact T070 high-budget structural subset and the same `prior_value`
student/search semantics.

| Input | Frozen identity |
|---|---|
| T079 STSRL base | `main` at Planner publication |
| accepted native baseline | `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083` |
| T070 high-budget subset manifest SHA-256 | `ec9201b87abb9921decdc337689b7a08e84899d4f01fd8b04172d21c9db8207c` |
| T070 high-budget subset cohort SHA-256 | `2d21a79dcbb393e4691e5aaf15f66c87fa20ba3e274bfa19baa30693cb2f029d` |
| T052 93-record cohort SHA-256 | `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608` |
| T043 checkpoint SHA-256 | `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4` |
| information regime | `full_simulator_state_oracle_like` |
| action space | inherited T070/T062 no-potion Search v2 action space |
| root selection | `highest_mean` |
| guided arm | `prior_value` with accepted T069 projection semantics |
| budgets | `100`, `400`, `1600` native tree-search playouts |

The exact 16-record subset must be reused if its retained artifact is available.
If the compact subset artifact is unavailable, it may be reconstructed only by
the frozen T070 outcome-blind rule from the exact T052 cohort and must reproduce
both published T070 subset hashes before execution. No substitute records are
allowed.

The T043 checkpoint must match the published SHA-256. T079 does not authorize a
replacement checkpoint or retraining.

## Research Hypothesis

Let a Search v2 path node be one node in the current path-indexed search tree.
Let an exact future-combat state be a native battle state whose complete
future-dynamics-relevant contents are equal, including hidden simulator state and
RNG state.

The hypothesis is:

> As Search v2 budget increases, a material share of new path-node expansions
> revisit exact future-combat states already represented elsewhere in the same
> search tree, so path-tree growth substantially overstates distinct-state
> exploration.

This is a representation hypothesis, not a learned-guidance hypothesis. T079
must be able to falsify it.

## Exact-State Identity Contract

T079 must define one native exact-state identity suitable for **diagnostic
comparison only**.

The identity must satisfy all of the following:

1. It is computed from the full native combat state at a Search v2 node, not from
   the public projection, model feature vector, action history, path string, or
   tree-node address.
2. Equality must preserve every value that can change future legal actions,
   transition probabilities, damage/resource outcomes, card/pile behavior,
   monster behavior, or RNG-dependent continuation under the current simulator.
3. Hidden draw/order information and all relevant RNG state are part of exact
   identity whenever they affect future dynamics.
4. A digest may be used for aggregation, but hash equality alone is not the
   semantic definition. The implementation must provide a canonical equality
   payload or an equivalent collision-check mechanism sufficient to reject a
   digest collision.
5. No field may be canonicalized as order-insensitive unless the native game
   semantics already make that ordering future-irrelevant. T079 must not invent
   strategy-level or card-specific equivalence rules.
6. Identity instrumentation is observation-only. It cannot be queried by node
   selection, expansion, rollout, backup, root selection, or learned callbacks.

If a future-dynamics-complete identity cannot be established and verified, T079
is incomplete and no representation conclusion may be published.

## Native Telemetry Surface

Add the narrowest read-only Search v2 companion needed to report state
utilization. Existing Search v2 methods and semantics remain unchanged.

For each expanded path node, telemetry must make it possible to recover at least:

- search-call identity;
- path-node expansion ordinal;
- tree depth;
- exact-state identity/digest;
- whether this exact state was first seen earlier in the same search call;
- first-seen expansion ordinal and depth for duplicates;
- a path fingerprint sufficient to prove that duplicate states were reached by
  distinct action paths, without using that fingerprint as state identity.

The implementation may aggregate online instead of retaining every raw native
state. It must retain enough evidence to validate duplicate groups and the exact
reported counts.

Telemetry must also preserve the existing T070 geometry fields so path-node,
edge, and exact-state measurements can be joined for the same search call.

## Semantic-Parity Gate

Before scientific execution, the telemetry-enabled companion must prove that it
is read-only.

For deterministic matched inputs, stripping the new telemetry must leave the
existing search result unchanged, including at least:

- selected root action;
- root visits and evaluation statistics;
- existing Search v2 internal telemetry;
- existing T070 tree geometry;
- policy-prior callback count and learned-value callback count;
- terminal/search status and simulator-step accounting.

Parity must cover `prior_value` with both callbacks enabled. Any material search
result difference blocks T079 execution.

## Scientific Execution

Run exactly three stages over the frozen ordered 16-record T070 high-budget
subset:

| Stage | Arm | Budget |
|---|---|---:|
| S100 | `prior_value` | 100 |
| S400 | `prior_value` | 400 |
| S1600 | `prior_value` | 1600 |

Each stage evaluates every ordered record once using the inherited T070
restored-battle execution and information regime. Use 16 one-record shards and
16 effective workers unless a documented simulator/memory constraint accepted by
Maintainer requires fewer; reported `worker_count` must denote effective
concurrent execution under the repository rule.

No baseline, `prior_only`, or `value_only` arm is required. The scientific target
is the path-tree representation used by the T070 `prior_value` high-budget result
that failed to produce a high-budget guidance signal.

T079 may report wins and selected actions only as semantic-parity/context fields.
They are not promotion evidence and no outcome gate is evaluated.

## Required State-Utilization Metrics

For every search call, and separately for each record's **first root search**,
report:

```text
expanded_path_nodes
unique_exact_states
exact_duplicate_path_nodes = expanded_path_nodes - unique_exact_states
exact_duplicate_fraction = exact_duplicate_path_nodes / expanded_path_nodes
unique_state_yield = unique_exact_states / expanded_path_nodes
```

Also report:

- duplicate-group count;
- multiplicity distribution (`paths_per_exact_state`: mean, median, p90, max);
- number and fraction of duplicate groups reached through distinct parent/action
  paths;
- duplicate expansions by depth;
- first-seen depth versus duplicate depth;
- top repeated exact-state groups by multiplicity, with occurrence-safe path
  fingerprints but no unnecessary full hidden-state dump;
- existing expanded-node and edge geometry for the same calls;
- native steps, model calls, wall time, and failure counts.

Aggregate each metric by budget across:

1. the 16 first-root searches, which share the same restored starting states
   across budgets; and
2. all Search v2 calls encountered during the 16 complete restored battles for
   that budget.

Keep these two populations separate.

## Cross-Budget Prefix And Marginal-Yield Audit

For the first-root search of each record, compare the ordered expansion-identity
sequence at budgets 100, 400, and 1600.

When the current search is deterministic under the frozen state/seed and the
shorter sequence is an exact prefix of the longer sequence, report:

```text
marginal_unique_yield_100_400
  = exact states first appearing in expansions 101..400 / 300

marginal_unique_yield_400_1600
  = exact states first appearing in expansions 401..1600 / 1200
```

Also report marginal duplicate fractions for those intervals.

If prefix equality fails for a record, report the failure explicitly and do not
fabricate marginal-yield values for that record. Per-budget duplicate metrics
remain valid. If fewer than 12/16 records satisfy prefix comparability, the
precommitted support/falsification classification below is `AMBIGUOUS` rather
than being computed from a small selected subset.

## Precommitted Interpretation Bands

T079 publishes exactly one of three diagnostic classifications. These bands are
frozen before scientific execution and must not be retuned after seeing results.

### `MATERIAL_EXACT_TRANSPOSITION_SIGNAL`

Require all of:

1. at least 12/16 first-root records are prefix-comparable;
2. median first-root `exact_duplicate_fraction` at budget 1600 is at least
   `0.20`;
3. median first-root `marginal_unique_yield_400_1600` is at most `0.80`;
4. at least 8/16 first-root records have budget-1600 duplicate fraction at least
   `0.15`;
5. at least 8/16 first-root records contain an exact state reached through two or
   more distinct action paths.

Interpretation: exact state transposition is a materially supported candidate for
a subsequent implementation/feasibility task. T079 itself does not implement or
publish that successor.

### `EXACT_TRANSPOSITION_SIGNAL_WEAK`

Require all of:

1. at least 12/16 first-root records are prefix-comparable;
2. median first-root `exact_duplicate_fraction` at budget 1600 is at most
   `0.05`;
3. at least 12/16 first-root records have budget-1600 duplicate fraction at most
   `0.10`;
4. median first-root `marginal_unique_yield_400_1600` is at least `0.90`;
5. no more than 2/16 first-root records have budget-1600 duplicate fraction above
   `0.20`.

Interpretation: literal/exact state transposition is not supported as the primary
explanation for T070's high-budget failure on this cohort. Planner should not
publish an exact-transposition implementation solely from the current evidence.

### `AMBIGUOUS`

Any valid result that satisfies neither band, or has fewer than 12
prefix-comparable first-root records, is `AMBIGUOUS`.

Interpretation: T079 does not justify an exact-transposition implementation. The
report must identify whether ambiguity comes from mixed duplicate burden,
non-prefix search stochasticity, depth concentration, or another measured
factor, and return the evidence to Planner.

These classifications are diagnostic only. They do not promote Search v2 or a
learned controller.

## Failure Boundary

T079 is fail-closed.

Stop without a representation classification if any of the following occurs:

- exact-state identity completeness/equality cannot be established;
- telemetry changes search semantics under the parity gate;
- frozen cohort/checkpoint identities cannot be verified;
- a required stage is incomplete or mixes source/native/model provenance;
- restored-state fidelity regresses after T078;
- the instrumentation would require using state identity to alter search itself.

Operational repair may continue on T079 only when it preserves the published
scientific contract. A material scientific or identity change returns to Planner
for reapproval.

## Out Of Scope

- adding a transposition table or merging search nodes;
- changing UCT/selection, expansion, rollout, backup, root selection, or budget;
- Beam search or another search topology;
- capability/diversity lanes or handcrafted offense/defense/scaling heuristics;
- changing policy priors, learned value use, model architecture, checkpoint,
  features, targets, or training;
- public-consistent hidden-future sampling or T063 execution;
- T075/T077 non-combat continuation;
- complete-run reachability or natural A20 scale-up;
- human trajectories, labels, card rankings, deck archetypes, or strategy rules.

## Outputs And Retention

Produce compact versioned outputs for at least:

- native/adapter state-identity and telemetry preflight;
- frozen T079 experiment manifest;
- per-stage execution evidence;
- per-record/per-search-call state-utilization rows;
- first-root cross-budget comparison;
- aggregate state-utilization report;
- terminal diagnostic classification;
- retention manifest.

Use a stable ignored artifact root such as:

```text
artifacts/t079-battle-search-state-utilization-diagnostic/
```

Retain exact input identities, stage commands, worker/shard evidence, compact
state-utilization rows, aggregate reports, diagnostic classification, hashes,
and regeneration instructions. Raw hidden-state equality payloads should not be
retained when hashes plus bounded collision/equality evidence are sufficient.

## Acceptance Criteria

1. T078 restore fidelity remains passing on the exact inputs consumed by T079.
2. A future-dynamics-complete native exact-state identity is documented and
   verified; public/model/path identity is not substituted for it.
3. The new telemetry surface is observation-only and passes exact semantic parity
   after telemetry removal.
4. The exact T070 16-record high-budget subset and exact T043 checkpoint are
   verified with no substitutions.
5. S100, S400, and S1600 each cover all 16 ordered records exactly once with
   complete provenance and effective-worker evidence.
6. Required path-node, unique-state, duplicate, multiplicity, depth, compute, and
   failure metrics are complete for every Search v2 call and first root.
7. Cross-budget prefix comparability and marginal-yield values are reported only
   where justified by exact sequence evidence.
8. Exactly one precommitted classification is produced without threshold
   retuning.
9. No search behavior, model, training data, source cohort, accepted scientific
   result, or promotion state is changed.
10. T079 publishes no successor task.

## Required Verification

Run the repository standard local gates plus:

- exact-state identity/equality tests, including collision fail-closed behavior;
- telemetry-off versus telemetry-on Search v2 parity with both callbacks enabled;
- existing T070 tree-geometry invariant tests;
- T078 restore-fidelity regressions relevant to consumed restored states;
- frozen subset/checkpoint identity tests;
- stage completeness and effective-worker tests;
- metric reducer and interpretation-band truth-table tests;
- WSL native source verifier if the fork integration changes;
- `git diff --check`.

If T079 requires a new `sts_lightspeed` integration for the read-only telemetry,
the normal T017/T020 source-manifest ownership applies. The PR must report both
the pre-task baseline integration and the exact new accepted native identity.

## Deliverables And PR Evidence

The final PR report must include:

- approved specification commit and exact implementation/run head;
- STSRL and native integration identities;
- exact-state identity semantics and validation evidence;
- telemetry semantic-parity result;
- frozen input hashes;
- exact stage commands, worker/shard topology, wall time, and failures;
- first-root and all-decision state-utilization summaries by budget;
- prefix-comparability count;
- precommitted classification and every threshold input;
- retained artifact/report hashes;
- explicit confirmation that no transposition/search-semantic/model/training or
  promotion change occurred.

## Successor Boundary

T079 does not publish its successor.

After T079 is accepted and merged, Planner re-evaluates the result:

- a `MATERIAL_EXACT_TRANSPOSITION_SIGNAL` may justify a separate bounded
  transposition-feasibility/implementation task;
- an `EXACT_TRANSPOSITION_SIGNAL_WEAK` result shifts attention away from exact
  path-state duplication toward other breaks already identified in the learning
  loop, such as retention/scalar-search representation or Oracle-to-public target
  ambiguity;
- an `AMBIGUOUS` result requires a new explicitly scoped diagnostic rather than
  silently implementing transposition.