# T088: Classical Combat Search Baseline Tournament

## Objective

Identify the strongest credible **non-learned Battle search baseline** that should be frozen for the next self-generated Non-Combat learning round.

T087 made Battle quality observable but did not improve the controller. T088 now asks one falsifiable question:

> On the exact accepted matched Battle-start distribution, does a classical non-learned search controller provide a reproducible Battle-quality improvement over the accepted unguided Search-v2@100 baseline, after accounting for dense T087 diagnostics and actual simulator/search cost rather than nominal search-budget labels alone?

This task is a baseline tournament, not a learned-policy experiment. It does not reopen the closed learned Battle value round, the closed root-prior allocation-repair route, or T079 exact-transposition instrumentation.

A successful T088 result may freeze a stronger non-learned Battle baseline. It does **not** establish a learned Battle improvement, a deployment-ready public-information controller, or complete-run A20 Heart performance.

## Publication Baseline

Planner publication base:

`main @ 10d44f962de44dfd51e17bc27c5dc9a7f988e76a`

Accepted canonical native identity at publication:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 96052d24b9c2c16ff25b6f7241edd972613be997`

Accepted predecessor:

- T087 / PR #100: `DENSE_COMBAT_DIAGNOSTICS_READY`;
- approved T087 material specification head: `81509bd426c9d0980e9a60ad28e9abb0ee0444e4`;
- accepted T087 implementation/run head: `8d7e449b2e13cdf271cbf7585f7cddbb3fee7d6e`;
- exact 413-record formal natural evidence SHA-256: `7931a118a4bf921f695db769f05fd77a5ae364484f5646f02d5be05329ad297f`;
- T087 final report SHA-256: `9a0eba7eed03a1ba4801c3019e9d14a2aa61214a76299a63ed9ab5a0192f3ea0`;
- T087 retention manifest SHA-256: `5afe39476965a192c9bdd8d6bed121cd0169e68925cabfe9b8366ee320938adc`.

T086 / PR #99 remains deferred and is not executable. T088 must complete before a new Non-Combat learner contract is published against a frozen Battle baseline.

## Research-Ledger Link

T088 is the second and third step of the accepted post-T085 sequence in issue #85:

1. T087 dense Combat diagnostics — complete;
2. classical Combat baseline tournament — this task;
3. freeze the strongest credible non-learned Combat baseline — this task's Planner acceptance consequence;
4. only then republish/materially amend the minimal self-generated Non-Combat learner;
5. true Battle/Non-Combat co-evolution remains downstream of independent local improvement evidence on both sides.

## Closed-Route Boundaries

The following are explicitly out of scope:

- learned policy priors;
- learned leaf values;
- further root-prior temperature/allocation/guardrail repair;
- exact transposition-table implementation or new T079-style exact-state identity rescue;
- model training or retraining;
- human action labels, human card/deck rankings, human imitation targets;
- complete-run Non-Combat policy changes;
- using T087 dense diagnostics as a learned reward, learned value target, Search training label, or single scalar promotion score.

Transparent handcrafted search heuristics are permitted only as named classical-search baseline components under the exact definitions below.

## Dependencies

Required accepted dependencies:

- T005: fixed structural Battle evaluation substrate;
- T012/T018: structured Battle outcome and terminal visible-resource identities;
- T016: public-context/replay audit semantics;
- T052: retained difficult later-act/Boss Battle coverage;
- T062: Search-v2 controller/search telemetry substrate;
- T078: restore/public/legal-action fidelity;
- T081: artifact eligibility gate;
- T085: accepted unguided Search-v2@100 and Search-v2@400 historical evidence;
- T087: exact 413-record matched cohort, amended terminal-monster semantics, dense diagnostic surface, cost/audit retention contract.

T088 must reuse the accepted restore/source identity path. It must not recreate a looser replacement cohort or silently drop records that are difficult for a challenger.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

### Inputs

Required scientific inputs are:

- exact T087 413-record selected Battle-start identities and ordering;
- exact T087/T085 restore and canonical-source bindings needed to restore those records;
- exact current canonical native identity and source-manifest binding;
- exact accepted Search-v2 controller semantics;
- exact T087 terminal-resolution diagnostic semantics;
- all T088 controller-definition, canary, formal per-record, cost, blind-audit, report, and retention artifacts.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T088 may claim only comparative Battle-controller evidence on the frozen matched Battle-start distribution and may freeze one non-learned Battle baseline for subsequent simulator-side source generation.

T088 does not claim:

- complete-run A20 improvement;
- Heart win-rate improvement;
- deployability in the live game;
- learned-policy improvement;
- correctness of any dense diagnostic as a reward/value target;
- correctness of a handcrafted heuristic beyond its role as a tournament baseline component.

### Required predicates

For the scientific-quality claim require:

- exact artifact identity, kind, SHA-256, and schema for every retained required input/output;
- exact 413-record cohort identity and ordering;
- exact A/B/C coverage of 93/192/128 records for **every formal arm**;
- exact restore/public/legal-action parity before each formal arm execution;
- exact controller configuration and implementation identity per arm;
- exact native identity and source verification;
- complete outcome and T087 dense diagnostic rows for all formal records/arms;
- complete resource-accounting fields defined below;
- no record substitution, outcome-conditioned retry, or arm-specific record omission;
- no smoke/debug/canary artifact used as representative tournament evidence.

### Unavailable-fact behavior

Missing, malformed, conflicting, filename-inferred, default-inferred, or unavailable required identities, raw fields, controller configuration, restore facts, cost counters, formal rows, hashes, schemas, or provenance fail closed to `INCOMPLETE`.

A controller may not be promoted by filling missing cost or diagnostic evidence with nominal-budget assumptions.

## Frozen Information Boundary

All four tournament arms operate in the same simulator-side Battle-search information class as the accepted native Search-v2 baseline: `full_simulator_state_oracle_like` for forward simulation.

This classification is explicit because native Search v2 copies the actual simulator state, including hidden simulator state needed for deterministic forward simulation. T088 therefore evaluates a **training/source-generation Battle planning baseline**, not a final deployed public-information controller.

For the new handcrafted heuristic components, the heuristic itself may consume only the following Battle-state quantities from a hypothetical search state:

- player current HP and max HP;
- player block;
- current turn number;
- current HP/max HP of Battle-active (`targetable`) enemies.

The heuristic must not read hidden future encounters, unrevealed future cards, hidden draw order as a feature, hidden Act-3 second-Boss identity, or raw RNG state as a scoring feature. Simulator transitions may still use the exact copied native state, as Search v2 already does.

## Common Battle Execution Contract

Every formal arm uses:

- action space: `ActionSpaceConfig.initial_no_potions()`;
- the exact restored checkpoint/RNG state for each record;
- no post-restore reseed or reset;
- no additional Python/controller/per-record Search seed;
- controlled-run boundary equivalent to accepted T085/T087 execution, including `seed=None` and `max_steps=200`;
- no learned policy/value callbacks;
- authoritative terminal Battle outcome from the simulator;
- T087 amended terminal-monster interpretation, including Battle-active=`targetable` and the active-unresolved enemy-HP definition.

The same restored record must be used independently for each arm. Arm execution order must be deterministic and retained; it must not depend on prior arm outcome.

## Required Tournament Arms

The formal tournament has exactly four required arms.

### Arm A — accepted Search v2 @100

Frozen current baseline:

- controller: native `BattleScumSearcher2` / Search v2;
- simulations: `100`;
- root selection: `highest_mean`;
- policy prior: none;
- learned leaf value: none;
- rollout: `BattleScumSearcher2::playoutRandom`;
- terminal utility: `BattleScumSearcher2::evaluateEndState`;
- action space: `initial_no_potions`.

This is the reference arm for baseline replacement.

### Arm B — Search v2 @400

Exact compute-scaling comparator:

- identical semantics to Arm A;
- simulations: `400`;
- every other controller/search setting identical to Arm A.

Arm B tests whether the historical positive high-budget signal survives the full T087 matched diagnostic surface. It must not be described as an algorithmically new controller.

### Common handcrafted state heuristic H1

Arms C and D may use exactly one transparent handcrafted nonterminal state heuristic, `combat_handcrafted_h1`.

For a nonterminal hypothetical Battle state define:

```text
player_hp_fraction = player_current_hp / player_max_hp

active_enemy_hp_fraction =
    sum(current_hp for targetable enemies)
    / sum(max_hp for targetable enemies)
```

If no targetable enemies remain, `active_enemy_hp_fraction = 0`.

Define bounded block and turn terms:

```text
block_fraction = player_block / (player_max_hp + player_block)
turn_fraction = min(max(turn, 0), 20) / 20
```

Then:

```text
h_raw =
    2.0 * player_hp_fraction
  - 2.0 * active_enemy_hp_fraction
  + 0.5 * block_fraction
  - 0.1 * turn_fraction

combat_handcrafted_h1 = tanh(h_raw)
```

The raw components and final heuristic value must be auditable in implementation tests.

This heuristic is a classical search-baseline component only. It is not a learned target, expert label, card ranking, dense T087 metric replacement, or future supervision artifact.

### Arm C — bounded Beam / weighted best-first baseline

Arm C is named `beam_h1_w32_b400_v1`.

It is intentionally **not** called A* because there is no admissible heuristic/path-cost contract.

Required semantics:

- layerwise Beam Search over controlled Battle action successors;
- beam width = `32`;
- global successor-transition budget per root decision = `400`;
- deterministic legal-action enumeration order inherited from the accepted ordered legal-action surface;
- terminal states are ranked ahead of nonterminal states by authoritative outcome, with player victory preferred over undecided and player loss ranked below undecided;
- within the same terminal-status class, nonterminal/undecided states rank by `combat_handcrafted_h1` descending;
- ties break by shorter action-sequence length, then exact ordered action-index sequence lexicographically;
- after each layer, keep at most the top 32 frontier states;
- stop when a player-victory frontier state is available at the completed layer, no frontier remains, the successor-transition budget is exhausted, or the controlled-run action boundary would be exceeded;
- select the first root action of the highest-ranked retained path.

A successor-transition budget counts each application of one legal Battle action to one copied/hypothetical simulator state exactly once.

No transposition table, learned evaluator, hidden-state hash bonus, card/deck ranking, or expert action prior is allowed.

### Arm D — progressive-bias classical MCTS @400

Arm D is named `progressive_bias_mcts_h1_400_v1`.

It must remain recognizably MCTS/UCT but must be algorithmically distinct from current Search v2 rather than a rename.

Required semantics:

- simulations per root decision = `400`;
- tree statistics: visit count and backed-up mean native terminal utility;
- terminal continuation utility and random rollout semantics remain `BattleScumSearcher2::evaluateEndState` and `BattleScumSearcher2::playoutRandom`;
- no learned prior or learned leaf value;
- root selection after simulations = highest backed-up mean, with deterministic ordered-action tie-break;
- base tree policy is UCT/UCB-style exploitation plus exploration;
- additionally apply an all-node **progressive-bias** term from `combat_handcrafted_h1` for each child state;
- progressive-bias weight = `0.50`;
- required bias form:

```text
progressive_bias =
    0.50 * combat_handcrafted_h1(child_state)
    / (1 + child_visit_count)
```

- the progressive-bias term therefore decays to zero as a child is repeatedly visited;
- the term is applied at every searchable tree node where the child heuristic is available, not only at the root.

The exact UCT normalization/exploration term must either reuse the current Search-v2 UCT term byte-for-byte or be frozen in an approved material amendment **before** canary. Silent exploration-formula drift is not allowed.

This arm is scientifically distinct from the closed root-prior allocation-repair route because it uses a fixed transparent handcrafted state heuristic as a decaying all-node classical progressive-bias term. It does not consume the historical learned root priors and does not create a new root-prior temperature/guardrail variant.

## Search-v2 / Arm-D Algorithmic-Difference Audit

Before canary, implementation evidence must demonstrate that Arm D is not merely current `BattleScumSearcher2` with a different label.

At minimum retain tests or bounded traces proving:

- Search v2 A/B have no H1 progressive-bias contribution;
- Arm D computes H1 on child states;
- Arm D applies the exact `0.50 * H1 / (1+n)` term beyond the root on at least one depth > 0 decision node;
- the bias decays with repeated visits;
- disabling the bias recovers the frozen Search-v2 tree-policy term under otherwise identical settings.

Failure to establish this difference blocks tournament execution.

## Native-Governance Boundary

No game-mechanics native change is authorized by T088.

Forbidden native changes include changes to:

- RNG behavior;
- legal-action semantics;
- card/monster/potion mechanics;
- Battle/game transitions;
- checkpoint/restore semantics;
- terminal outcome;
- `evaluateEndState` semantics;
- hidden/public-information semantics.

Implementation should prefer STSRL-side controllers over existing exact native transition/restore bindings when practical.

If Arm D or required cost telemetry requires a native search-semantic change, that change is high-risk under native governance because it touches search expansion/selection/backup/root behavior. It must therefore:

1. use a temporary `work/T088-*` native branch;
2. record exact `native_base` and `native_result`;
3. receive an independent native semantic review before scientific canary;
4. land on canonical `refs/heads/stsrl/main`;
5. prove `native_base --is-ancestor-of--> native_result`;
6. update the STSRL source manifest to the exact canonical descendant;
7. revalidate the frozen A/B Search-v2 behavior on bounded parity records.

A temporary native work branch may never be a formal STSRL build input.

## Formal Cohort

Formal evaluation uses the exact complete T087 natural cohort with no reselection:

- Cohort A: 93 records;
- Cohort B: 192 records;
- Cohort C: 128 records;
- total: 413 records.

Every required arm must execute all 413 exact occurrence-safe identities in the same canonical record order.

No formal record may be dropped because an arm is slow, loses, encounters dynamic monster occurrences, or produces an inconvenient dense metric.

If a required arm cannot complete one record under the approved resource/runtime contract, the formal tournament is incomplete unless Maintainer authorizes a task-level material amendment. Do not substitute a neighboring record.

## Dense Diagnostic Contract

T088 must reuse the final accepted **amended** T087 diagnostic semantics rather than the superseded original formulas.

Per record/arm retain at minimum:

- authoritative Battle outcome;
- player start/current/max HP and terminal HP;
- Battle-start enemy HP evidence;
- `enemy_occurrence_count_terminal`;
- `enemy_count_active_terminal`;
- `enemy_count_hp_alive_terminal`;
- `enemy_count_non_targetable_hp_alive_terminal`;
- `terminal_total_enemy_hp_all_occurrences`;
- `terminal_total_enemy_hp_active`;
- loss-side `enemy_hp_remaining_fraction` using active unresolved HP only;
- `enemy_hp_progress_fraction_v1`;
- win-side `player_hp_remaining_fraction_of_max`;
- `net_player_hp_delta`;
- `combat_terminal_margin_v1` as diagnostic only;
- controlled Battle actions/turns when available under the retained T087 contract;
- exact terminal monster raw rows needed to recompute the above.

Do not restore `enemy_count_killed`, `enemy_kill_fraction`, or the superseded authoritative `enemy_damage_fraction` as promotion evidence.

Dense diagnostics are decomposed diagnostic evidence. T088 must not collapse them into one newly invented scalar controller score.

## Resource-Accounting Contract

Nominal `simulations=100`, `simulations=400`, or Beam `budget=400` are **not** treated as equal computational work.

For each record and each root decision retain, where applicable:

- controller/root decision count;
- nominal simulation/budget parameter;
- native/search successor transition count;
- native simulator steps under the existing canonical telemetry definition when available;
- tree node expansion count;
- rollout count;
- terminal utility evaluation count;
- action-execution count;
- model calls, required to be zero;
- wall-clock seconds measured by monotonic/perf-counter timing;
- worker identity and stage worker count;
- peak process memory if the existing execution harness exposes it reliably without adding a new scientific dependency.

The final report must include per-arm distributions and totals, not only aggregate means.

If an exact counter is not meaningful for one algorithm, report it as explicitly unavailable and retain the algorithm-specific exact work counters that replace it. However, every arm must have at least one directly counted simulator-transition/work measure plus wall-clock time. A missing generic work measure for an arm blocks any efficiency claim about that arm.

## Statistical Analysis

All controller-quality comparisons are paired by exact Battle-start identity.

Arm A is the frozen reference. Pairwise analyses are required for B-A, C-A, and D-A. The final report must also show B-C, B-D, and C-D for tournament interpretation.

### Binary outcome

For each pair report:

- wins per arm;
- paired discordant counts (`candidate_win/reference_loss`, `candidate_loss/reference_win`);
- paired win-rate difference;
- a deterministic 95% paired bootstrap confidence interval using 20,000 resamples of exact record identities with seed `880088`;
- exact McNemar test on discordant outcomes when the required counts are valid.

Bootstrap resampling must preserve complete arm pairing. It may additionally report cohort-stratified intervals, but the all-413 paired result is mandatory.

### Dense diagnostics

Report paired deltas without turning them into a single score.

At minimum:

- among records where both compared arms lose: paired delta in `enemy_hp_remaining_fraction`;
- among records where both compared arms win: paired delta in `player_hp_remaining_fraction_of_max`;
- all-record descriptive distribution of `combat_terminal_margin_v1`, clearly labeled diagnostic-only;
- outcome-transition table showing loss->win, win->loss, loss->loss, win->win;
- A/B/C cohort breakdowns for the above.

For paired continuous deltas report mean, median, deterministic paired-bootstrap 95% CI, and sample count.

Dynamic encounter/escape/summon/heal cases must remain in the analysis under the amended raw-evidence semantics; they may be separately diagnosed but not silently excluded.

## Baseline-Selection Rule

T088 does **not** create one weighted scalar score over win rate, dense diagnostics, and cost.

Instead use the following precommitted lexicographic evidence order.

### 1. Outcome evidence first

A candidate has **clear outcome superiority** over another arm only when the paired 95% CI for win-rate difference has lower bound `> 0`.

A candidate has **clear outcome harm** when the paired 95% CI upper bound is `< 0`.

Otherwise the binary outcome comparison is `OUTCOME_INCONCLUSIVE` for that pair.

### 2. Dense diagnostics resolve only outcome-inconclusive comparisons

If binary outcome is inconclusive, use the decomposed T087 diagnostics as tie-resolution evidence, not as a scalar score.

A candidate is `DENSE_DIRECTIONALLY_BETTER` only when all applicable statements hold:

- on both-loss records, the paired mean delta in `enemy_hp_remaining_fraction` is `< 0` and its 95% CI upper bound is `< 0`;
- on both-win records, if at least 8 paired wins exist, the paired mean delta in `player_hp_remaining_fraction_of_max` is `>= 0` or its CI includes zero; it must not show clear HP-retention harm;
- no T087 terminal-resolution consistency gate fails.

If these decomposed signals disagree, the dense comparison remains `DENSE_MIXED` rather than forcing a winner.

### 3. Cost breaks residual quality ties

If two controllers remain quality-tied after outcome and dense evidence, prefer the controller with lower directly measured simulator-transition work. If work is statistically/operationally indistinguishable, prefer lower wall-clock cost.

Do not prefer a faster arm that has clear outcome harm.

### 4. Promotion eligibility relative to Arm A

A challenger is eligible for Planner baseline replacement consideration only if:

- it has no scientific/provenance failures;
- it has no clear outcome harm versus Arm A;
- and either:
  - it has clear outcome superiority versus Arm A; or
  - outcome is inconclusive and it is `DENSE_DIRECTIONALLY_BETTER` versus Arm A.

This rule identifies **eligible** challengers. It does not automatically merge a new baseline into later tasks. Final baseline freezing still requires Planner scientific/architecture acceptance of the complete tournament evidence and Maintainer exact-head operational acceptance.

If more than one challenger is eligible and no unique controller is selected by the lexicographic rule, T088 must report a Pareto/tie set and Planner must not invent an unreported weighted score after seeing results.

## Search@400 Interpretation

Arm B is specifically required to answer whether the historical compute signal generalizes.

Possible interpretations include:

- Search@400 clearly improves outcome and/or resolves an outcome tie through dense diagnostics at acceptable measured cost;
- Search@400 changes dense terminal quality without sufficient evidence to replace Search@100;
- Search@400 provides no reproducible quality gain despite higher compute;
- Search@400 is stronger but operationally too costly for the next source-generation round, in which case the cost tradeoff must be stated explicitly rather than hidden by nominal simulation labels.

T088 must not call Search@400 the default merely because it uses more simulations.

## Canary Gate

No canary is authorized by specification approval alone.

After implementation review, Maintainer may authorize one bounded canary. The canary must exercise all four arms and include at least:

- the previously reproduced escaping-Mugger terminal case used by T087;
- one ordinary victory without an escaped positive-HP monster;
- one ordinary loss;
- one later-act/Boss record;
- at least one record with more than one legal root action.

Canary acceptance requires:

- exact restore/legal-action parity;
- all controller identities/configurations correct;
- A/B parity with frozen Search-v2 semantics;
- Beam deterministic tie-breaking/replay;
- Arm-D progressive-bias audit beyond root depth;
- T087 amended dense metrics recompute from raw terminal evidence;
- resource counters are finite/non-negative and internally consistent;
- no learned model calls;
- no native/game-mechanics drift.

Canary outcomes are runtime evidence only and may not be used to tune H1 weights, Beam width/budget, progressive-bias weight, or formal promotion thresholds.

A failed canary does not authorize free retry. Repair and retry require a new Maintainer authorization on the repaired exact head.

## Formal Execution Gate

Fresh formal tournament execution requires explicit Maintainer authorization after accepted canary evidence.

Formal execution must start from zero for all four arms. Do not reuse partial rows from a failed formal attempt.

Required formal matrix:

```text
413 exact records
x 4 required arms
= 1,652 complete natural Battle executions
```

Each arm must use the same accepted runtime/native build identity within the formal tournament unless a task-approved native lineage amendment explicitly requires otherwise. Mixed unrecorded native builds invalidate the tournament.

Parallel sharding is allowed only if record identity/order, per-row provenance, deterministic merge order, effective worker count, and worker failures are retained and validated.

## Blind Human Audit Bundle

After formal statistical analysis, generate one paired blind-audit bundle comparing Arm A with the highest-ranked eligible challenger, or with the highest-ranked non-A arm if no challenger is eligible.

The bundle is auxiliary diagnostic evidence and does not block the automated tournament classification if no human labels are returned before finalization.

Select at most 24 exact records in this order, using deterministic SHA-256 tie-breaking on `selection_identity` within each stratum:

1. up to 8 outcome-discordant records;
2. up to 8 both-loss records with the largest absolute difference in active-unresolved `enemy_hp_remaining_fraction`;
3. up to 8 both-win records with the largest absolute difference in player HP remaining fraction.

If a stratum has fewer than 8 records, do not backfill from a different semantic stratum beyond the 24-record cap.

For each record export both traces under blinded labels X/Y. The reviewer must not see:

- controller identity;
- Search budget;
- H1 score;
- dense diagnostic values;
- wall-clock/work counters;
- filenames that reveal the arm;
- hidden simulator state or RNG state.

Use the T087 rubric fields:

```text
start_winnability
combat_execution_quality
dominant_failure_source
earliest_decisive_step_or_turn
confidence_1_to_5
notes
optional_pairwise_preference
```

Retain a separate hidden provenance map. Human labels may inform Planner diagnosis but may not become policy/value targets, expert rankings, or the sole baseline-promotion gate.

## Required Retained Artifacts

At minimum retain exact identities/hashes for:

1. task/specification identity;
2. implementation/controller-definition manifest;
3. native source/build verifier and lineage evidence;
4. exact 413-record formal cohort manifest;
5. canary evidence;
6. formal raw per-record/per-arm rows;
7. formal resource/cost rows;
8. statistical comparison report;
9. blind paired trace bundle;
10. hidden blind-audit provenance map;
11. final tournament report;
12. retention manifest.

The final retention audit must verify path, byte count, SHA-256, schema/kind, exact task/controller/native provenance, and cross-artifact identity references.

## Terminal Classifications

T088 ends in exactly one of:

### `STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED`

At least one challenger is promotion-eligible relative to Arm A and the lexicographic rule plus complete cost evidence identifies a unique strongest credible non-learned baseline for Planner acceptance.

The final report must name the exact controller/configuration and whether the improvement came from:

- higher Search-v2 compute;
- Beam/weighted-best-first search;
- progressive-bias MCTS.

### `NO_CHALLENGER_CLEARS_PROMOTION_GATE`

The complete valid tournament finds no challenger eligible to replace Search-v2@100. Search-v2@100 remains the frozen Battle baseline. This is a valid negative result and must close the tested classical-search variants rather than trigger parameter patching inside T088.

### `TOURNAMENT_TIE_REQUIRES_PLANNER_DECISION`

At least two challengers are promotion-eligible, but the precommitted lexicographic evidence order does not identify a unique winner. The exact tied/Pareto set must be reported. Planner may either freeze one only with an explicit architecture/cost rationale grounded in the retained evidence or publish a new narrowly justified discriminator task. Do not invent an ex-post scalar score.

### `INCOMPLETE`

A required scientific/provenance/runtime/artifact gate fails or a required arm/record cannot produce complete admissible evidence.

Operational/runtime failure is not evidence for or against an algorithm.

## Post-T088 Research Consequence

After a valid terminal result and final Planner/Maintainer acceptance:

- freeze the selected strongest credible non-learned Battle baseline on `main`;
- update issue #85 with the exact accepted controller identity and claim boundary;
- do **not** reopen the T085 learned Battle value round merely because a classical controller wins;
- re-review the deferred T086 idea against the newly frozen Battle baseline;
- publish a fresh or materially amended minimal self-generated Non-Combat learner contract;
- only after independent Non-Combat improvement and richer natural occupancy should Battle local-learnability be reopened under a new mechanism hypothesis.

## Workflow And Authorization

Default serial one-task/one-PR workflow applies.

1. Planner publishes this complete contract on a fresh branch/PR from synchronized `main`.
2. No implementation or scientific execution may begin before exact-head Maintainer approval:

```text
SPEC APPROVED

task: T088
approved_spec_commit: <full SHA>
implementation_authorized: true
```

3. Implementation continues on the same PR.
4. Ordinary implementation commits do not invalidate the approved specification.
5. Any material controller definition, heuristic, formal cohort, promotion rule, information boundary, native-search semantics, or statistical-contract change requires Planner amendment and new exact-head Maintainer approval.
6. Implementation review must pass before canary authorization.
7. Canary acceptance must pass before formal authorization.
8. Failed/partial canary or formal rows are not scientific evidence and do not authorize free retry.
9. Terminal report, classification, lifecycle/docs, and retention stay on the same PR.
10. Final landing requires Maintainer operational/exact-head acceptance and Planner scientific/architecture acceptance on the same final head.
11. Merge uses expected-head locking; `main` remains durable truth.

## Acceptance Checklist

T088 is acceptable only when all of the following hold:

- exact current publication base and native identity are recorded;
- T087 accepted artifacts are identity/hash-bound;
- all four required arms are implemented exactly;
- Arm D is proven algorithmically distinct from Search v2;
- no learned policy/value/root prior is consumed;
- H1 is exact, transparent, auditable, and used only as a classical search component;
- no closed-route root-prior/transposition repair is reopened;
- native governance is respected for any search-semantic native change;
- canary was independently authorized and accepted;
- fresh formal execution contains exactly 413 matched records for each arm;
- all 1,652 formal executions have complete provenance, outcome, T087 diagnostics, and cost evidence;
- binary and dense paired analyses follow the precommitted statistical contract;
- no nominal simulation count is treated as equivalent work without measured counters;
- blind audit bundle is properly blinded and separated from provenance;
- T081 scientific-quality eligibility passes;
- final report has one terminal classification and no unsupported claim expansion;
- final baseline freeze, if any, is supported by the precommitted evidence order and exact controller identity.
