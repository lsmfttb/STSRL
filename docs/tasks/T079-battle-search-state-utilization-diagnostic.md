# T079: Battle Search State-Utilization Bounds Recovery

## Objective

Recover the T079 representation diagnostic after PR #83 proved that requiring a
future-dynamics-complete exact identity for **every** Search v2 path node is the
wrong abstraction for the current native simulator.

T079 still asks the same scientific question raised by T070: does the current
path-indexed Search v2 spend a material share of additional budget revisiting
states already represented elsewhere in the same search tree? The recovery
answers that question with conservative exact-state bounds instead of requiring a
repository-wide semantic rewrite of opaque `ActionQueue` continuations.

This remains a measurement task. It does **not** implement transposition, merge
nodes, change search allocation, retrain a model, add Beam search, or alter any
controller promotion decision.

## Architecture-Recovery Baseline

T078 is complete after PR #82 and established trustworthy restored-state fidelity:
the exact retained 320-state restore-only audit passed with zero mismatches, no
candidate replacement, and no counterfactual continuation execution.

The first T079 implementation line on Draft PR #83 is architecture-rejected as a
scientific completion path. Its authoritative preflight produced no representation
classification. It established the following useful facts:

- the exact T070 16-record subset and T043 checkpoint were available and verified;
- T078 restore fidelity remained valid on the consumed 16 records;
- telemetry-off Search v2 execution remained healthy;
- real Search v2 path nodes can contain a non-empty future-relevant
  `ActionQueue` whose entries are type-erased
  `std::function<void(BattleContext&)>` values;
- the prototype correctly reported `identity_complete=false` rather than
  inventing equality for those queued continuations;
- no S100/S400/S1600 scientific stage and no
  `MATERIAL_EXACT_TRANSPOSITION_SIGNAL`, `EXACT_TRANSPOSITION_SIGNAL_WEAK`, or
  `AMBIGUOUS` classification was produced.

The native reason is structural. `search::Action::execute()` invokes
`BattleContext::executeActions()`. That executor can stop when a queued action
opens a player-input state while later queued continuations remain pending.
Consequently such opaque continuations are legitimate parts of some Search v2
path-node futures. Making all of them serializable would require explicit
semantic descriptors across more than seventy action/lambda creation sites and
all associated capture/copy/queue paths. T079 does not authorize that broad
native-model redesign.

PR #83 remains audit evidence only and must not be merged as T079 completion.
Safe observation-only primitives from that line may be reused only after they are
revalidated against this recovery contract.

## Dependencies

T078, T070, T069, T062, T052, T043, T017, and T020.

## Frozen Scientific Inputs

The scientific inputs are unchanged from the original T079 contract.

| Input | Frozen identity |
|---|---|
| recovery STSRL base | `main` at recovery publication |
| pre-T079 accepted native lineage anchor | `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083` |
| T070 high-budget subset manifest SHA-256 | `ec9201b87abb9921decdc337689b7a08e84899d4f01fd8b04172d21c9db8207c` |
| T070 high-budget subset cohort SHA-256 | `2d21a79dcbb393e4691e5aaf15f66c87fa20ba3e274bfa19baa30693cb2f029d` |
| T052 93-record cohort SHA-256 | `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608` |
| T043 checkpoint SHA-256 | `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4` |
| information regime | `full_simulator_state_oracle_like` |
| action space | inherited T070/T062 no-potion Search v2 action space |
| root selection | `highest_mean` |
| guided arm | `prior_value` with accepted T069 projection semantics |
| budgets | `100`, `400`, `1600` native tree-search playouts |

Reuse the exact ordered T070 16-record high-budget subset. If its retained compact
artifact must be reconstructed, the frozen T070 outcome-blind rule must reproduce
the published manifest and cohort hashes exactly. No replacement record is
allowed. The T043 checkpoint must match its published hash; no retraining or
checkpoint substitution is authorized.

## Recovered Identity-Evidence Contract

Every expanded Search v2 path node is classified into exactly one identity-evidence
class:

### `exact_comparable`

The node has a canonical native payload that is complete for future combat
dynamics under the current simulator. Equality must preserve every **active**
value that can change future legal actions, transition probabilities,
damage/resource outcomes, card/pile behavior, monster behavior, or RNG-dependent
continuation.

The comparable payload must include hidden draw/order state and all relevant RNG
state. A digest may be used for aggregation, but digest equality is not the
semantic definition; payload equality or an equivalent collision check is
required.

Queue/container identity is semantic rather than byte-layout identity:

- serialize active `CardQueue` items in execution order;
- serialize the active current card item when it can affect continuation;
- ignore inactive/stale container slots, allocator/capacity artifacts, process
  addresses, and debug-only counters that cannot affect future transitions;
- when `ActionQueue` is empty, inactive stored `std::function` objects and stale
  queue indices/bits are not part of future state and must not create false
  non-equality.

This avoids both false equality and false non-equality. The recovery must not use
an over-strict payload containing unreachable stale slots as evidence for a
`WEAK` result.

### `opaque`

Exact equality cannot be established for the node. A non-empty type-erased
future-relevant `ActionQueue` is the known initial reason, but any other genuinely
incomplete component must also fail into `opaque` rather than being guessed.

Opaque nodes:

- receive no exact-state equivalence class used for deduplication;
- are never silently treated as equal or unique;
- retain a reason category such as `opaque_action_queue`;
- may retain path/depth/ordinal telemetry, but process addresses,
  `std::function::target_type`, queue position, or path identity are not state
  equality substitutes.

High opacity is **not** an execution failure. It widens the scientific bounds and
therefore may force an `AMBIGUOUS` terminal result.

## Observation-Only Telemetry

Add or recover the narrowest read-only Search v2 telemetry needed to report, per
expanded path node:

- search-call identity;
- expansion ordinal;
- depth;
- path fingerprint/ordered action identity sufficient for cross-budget prefix
  comparison;
- identity-evidence class;
- opaque reason when applicable;
- exact digest and collision-checked equality evidence only for
  `exact_comparable` nodes.

Preserve existing T070 tree geometry so path growth and state-utilization bounds
can be joined for the same search call.

Identity evidence cannot be queried by selection, expansion, rollout, backup,
root selection, or learned callbacks.

## Semantic-Parity Gate

Before scientific stages, telemetry-off versus telemetry-on execution must prove
that instrumentation is observation-only. For deterministic matched `prior_value`
inputs with both callbacks enabled, stripping the recovery telemetry must leave
unchanged at least:

- selected root action;
- root visits and evaluation statistics;
- existing Search v2 internal telemetry;
- T070 tree geometry;
- policy-prior and learned-value callback counts;
- search/terminal status;
- simulator-step accounting.

Any material difference blocks scientific execution.

If the recovery uses a new `sts_lightspeed` integration, T017/T020 source-manifest
ownership applies. The PR must report the pre-task lineage anchor and exact new
active integration identity and pass the normal source verifier. A temporary
native work branch is not an accepted build input.

## Scientific Execution

Run exactly three stages over the frozen ordered 16-record T070 high-budget
subset:

| Stage | Arm | Budget |
|---|---|---:|
| S100 | `prior_value` | 100 |
| S400 | `prior_value` | 400 |
| S1600 | `prior_value` | 1600 |

Each stage evaluates all 16 records exactly once using the inherited T070 restored
battle execution and information regime. Use 16 one-record shards and 16
effective workers unless a concrete simulator/memory constraint accepted by
Maintainer requires fewer. Report actual effective concurrency under the
repository worker-count rule.

No baseline, `prior_only`, or `value_only` scientific arm is required. Outcome
fields may be retained only for parity/context; they are not promotion evidence.

## State-Utilization Bounds

For one Search v2 call define:

```text
N = expanded_path_nodes
C = exact_comparable_nodes
O = opaque_nodes = N - C
U = unique_exact_states_among_comparable_nodes
D = comparable_duplicate_nodes = C - U
```

Require the identity partition invariant `N = C + O` and `0 <= U <= C`.

Report:

```text
exact_duplicate_fraction_lower = D / N
exact_duplicate_fraction_upper = (D + O) / N = 1 - U / N

unique_state_yield_lower = U / N
unique_state_yield_upper = (U + O) / N
```

The lower duplicate bound assumes every opaque node is a new distinct state. The
upper duplicate bound allows every opaque node to be a duplicate of an already
represented or other opaque state. These are deliberate worst cases; no
probabilistic assumption about opaque nodes is permitted.

For comparable nodes additionally report descriptive evidence:

- exact duplicate-group count;
- multiplicity distribution;
- comparable exact states reached through distinct parent/action paths;
- duplicate expansions by depth;
- first-seen depth versus duplicate depth;
- top repeated comparable groups using occurrence-safe path fingerprints;
- digest collision count;
- opaque counts/fractions by reason and depth;
- existing geometry, native steps, model calls, wall time, and failure counts.

Report separately for:

1. each record's first-root Search v2 call; and
2. all Search v2 calls encountered during the complete restored battle at that
   budget.

Do not mix those populations.

## Cross-Budget Prefix And Marginal Bounds

For each record's first-root search, compare the deterministic ordered expansion
**path/action sequence** at budgets 100, 400, and 1600. Exact-state identity for
opaque nodes is not required to establish that the shorter traversal sequence is
an exact prefix of the longer traversal sequence.

A record is prefix-comparable only when the 100 expansion-path sequence is an
exact prefix of 400 and the 400 sequence is an exact prefix of 1600 under the
frozen search state/seed. Report the first mismatch when this fails.

For a prefix-comparable interval of length `L`, let:

```text
K = number of exact-comparable states whose first comparable occurrence in the
    full ordered expansion sequence appears inside this interval
O_i = number of opaque expansions in the interval
```

Then report:

```text
marginal_unique_yield_lower = K / L
marginal_unique_yield_upper = (K + O_i) / L
```

Use `L=300` for expansions 101..400 and `L=1200` for 401..1600. The lower bound
assumes no opaque interval expansion contributes a new state; the upper bound
allows every opaque interval expansion to contribute one.

Do not fabricate marginal bounds for non-prefix records. If fewer than 12/16
first-root records are prefix-comparable, the terminal classification is
`AMBIGUOUS`.

## Recovered Precommitted Classification

The original T079 numerical thresholds remain unchanged. Recovery changes only
which conservative side of an uncertainty interval must satisfy them.

### `MATERIAL_EXACT_TRANSPOSITION_SIGNAL`

Require all of:

1. at least 12/16 first-root records are prefix-comparable;
2. median first-root `exact_duplicate_fraction_lower` at budget 1600 is at least
   `0.20`;
3. median first-root `marginal_unique_yield_upper_400_1600` is at most `0.80`;
4. at least 8/16 first-root records have budget-1600
   `exact_duplicate_fraction_lower >= 0.15`;
5. at least 8/16 first-root records contain an `exact_comparable` state reached
   through two or more distinct action paths.

Interpretation: material exact path-state reuse is supported even under the most
transposition-unfavorable treatment of every opaque node. Planner may consider a
separate transposition feasibility task after T079 closes; T079 does not publish
or implement it.

### `EXACT_TRANSPOSITION_SIGNAL_WEAK`

Require all of:

1. at least 12/16 first-root records are prefix-comparable;
2. median first-root `exact_duplicate_fraction_upper` at budget 1600 is at most
   `0.05`;
3. at least 12/16 first-root records have budget-1600
   `exact_duplicate_fraction_upper <= 0.10`;
4. median first-root `marginal_unique_yield_lower_400_1600` is at least `0.90`;
5. no more than 2/16 first-root records have budget-1600
   `exact_duplicate_fraction_upper > 0.20`.

Interpretation: literal exact transposition remains weak even under the most
transposition-favorable treatment of every opaque node. Exact path-state reuse is
not supported as the primary explanation for T070's high-budget failure on this
cohort.

### `AMBIGUOUS`

Every otherwise-valid result satisfying neither conservative band is
`AMBIGUOUS`, including cases where opacity makes the bounds straddle the original
thresholds.

Interpretation: the current evidence cannot justify an exact-transposition
implementation. Report whether ambiguity is dominated by opacity, mixed duplicate
burden, non-prefix traversal, depth concentration, or another measured factor.

These classifications are diagnostic only and cannot promote Search v2 or a
learned controller.

## Failure Boundary

Stop without a representation classification if any of the following occurs:

- the `exact_comparable` canonical payload is not demonstrably complete for the
  active future state it claims to compare;
- a digest collision is not resolved by canonical equality;
- telemetry changes search semantics under parity;
- frozen cohort/checkpoint identities cannot be verified;
- T078 restore fidelity regresses on consumed inputs;
- S100/S400/S1600 is incomplete or mixes source/native/model provenance;
- instrumentation would need to change ActionQueue execution, search traversal,
  allocation, backup, rollout, root selection, or simulator game semantics.

A high `opaque` fraction alone is not a failure; it produces wider bounds and
possibly `AMBIGUOUS`.

No broad ActionQueue semantic-descriptor rewrite is authorized by T079 recovery.

## Out Of Scope

- semanticizing every native `ActionQueue` lambda/capture;
- adding a transposition table or merging search nodes;
- changing UCT/selection, expansion, rollout, backup, root selection, or budget;
- Beam search or another search topology;
- capability/diversity lanes or handcrafted combat heuristics;
- changing policy priors, learned value use, model architecture, checkpoint,
  features, targets, or training;
- public-consistent hidden-future sampling or T063 execution;
- T075/T077 non-combat continuation;
- complete-run reachability or natural A20 scale-up;
- human trajectories, labels, card rankings, deck archetypes, or strategy rules.

## Outputs And Retention

Use stable ignored root:

```text
artifacts/t079-state-utilization-bounds-recovery/
```

Produce compact versioned outputs for at least:

- recovery native/adapter telemetry preflight;
- frozen recovery experiment manifest;
- per-stage execution evidence;
- per-record/per-search-call identity-evidence counts and bounds;
- comparable-state duplicate/multiplicity/depth evidence;
- first-root cross-budget prefix and marginal-bound report;
- aggregate bounds report;
- terminal recovered classification;
- retention manifest.

Retain exact input identities, commands, worker/shard evidence, compact telemetry,
report hashes, regeneration instructions, and the provenance of any safe primitive
reused from #83. Raw hidden-state payloads need not be retained when bounded
collision/equality evidence is sufficient.

## Acceptance Criteria

1. T078 restore fidelity remains passing on the exact consumed inputs.
2. Every expanded node is accounted for exactly once as `exact_comparable` or
   `opaque`, with no equality claim for opaque nodes.
3. `exact_comparable` canonical identity is verified as future-dynamics-complete
   over active state, collision-safe, queue-order-aware, and free of inactive
   stale-slot/process-identity artifacts that could create false non-equality.
4. Telemetry is observation-only and passes the full `prior_value` parity gate.
5. The exact T070 16-record subset and T043 checkpoint hashes pass with no
   substitutions.
6. S100, S400, and S1600 each cover all 16 ordered records exactly once with
   complete provenance and effective-worker evidence.
7. `N/C/O/U/D`, duplicate/yield lower and upper bounds, opacity, comparable-state
   multiplicity/depth/path evidence, geometry, compute, and failures are complete
   for every search call and first root.
8. First-root prefix comparability and marginal-yield bounds are reported only
   where justified by exact path-sequence evidence.
9. Exactly one recovered MATERIAL/WEAK/AMBIGUOUS classification is produced with
   the original numerical thresholds and the conservative bound sides above; no
   post-result retuning is allowed.
10. No search behavior, simulator game semantics, model, training data, source
    cohort, accepted historical result, or promotion state is changed.
11. T079 publishes no successor task.

## Required Verification

Run the repository standard local gates plus:

- canonical comparable-state identity tests using independently constructed
  equal/different active states;
- active-versus-inactive CardQueue and empty-ActionQueue normalization tests;
- opaque ActionQueue fail-safe classification tests;
- digest collision fail-closed tests;
- telemetry-off/on Search v2 parity with both callbacks enabled;
- existing T070 geometry invariants;
- T078 restore regressions relevant to the 16 consumed records;
- exact frozen subset/checkpoint identity tests;
- stage completeness/effective-worker tests;
- bound arithmetic and median tests;
- prefix/marginal-bound tests;
- recovered classification truth-table tests;
- WSL native source verifier if the integration changes;
- `git diff --check`.

## Deliverables And PR Evidence

The final PR must report:

- recovery approved-spec commit and exact implementation/run head;
- #83 architecture-recovery disposition and any primitive reuse;
- STSRL and native integration identities;
- canonical `exact_comparable` semantics and opaque reason inventory;
- telemetry parity result;
- frozen input hashes;
- exact stage commands, workers/shards, wall time, and failures;
- first-root and all-call bounds by budget;
- opacity rates and comparable-state duplicate evidence;
- prefix-comparable count and marginal bounds;
- every input to the recovered precommitted classification;
- retained artifact/report hashes;
- confirmation that no broad ActionQueue rewrite, transposition, search-semantic,
  model/training, or promotion change occurred.

## Successor Boundary

T079 recovery does not publish a successor.

After merge, Planner re-evaluates the terminal evidence:

- `MATERIAL_EXACT_TRANSPOSITION_SIGNAL` may justify a separate bounded
  transposition-feasibility task;
- `EXACT_TRANSPOSITION_SIGNAL_WEAK` shifts priority away from literal exact
  path-state duplication toward other learning-loop breaks;
- `AMBIGUOUS` requires a new explicitly scoped diagnostic or a decision that the
  remaining uncertainty is not worth resolving before testing another bottleneck.
