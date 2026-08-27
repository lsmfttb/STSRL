# T075: Leakage-Safe Non-Combat Cohort Repair

## Normative Specification Bundle

This task document defines the scientific scope and lifecycle of T075. The exact execution, retained-input, artifact-schema, command, sharding, retention, and failure contract is a normative part of this task and is published at:

[`T075-frozen-execution-artifact-contract.md`](T075-frozen-execution-artifact-contract.md)

Both files must be reviewed at the same exact proposal head. If this document is less specific about an execution/artifact detail, the linked normative contract controls. Any material change after exact-head approval requires Maintainer re-approval.

## Objective

Repair the single cohort-partition defect exposed by T065 Case D and continue the otherwise unchanged learned non-combat experiment from the accepted T065 Stage 1 source evidence.

T065 remains `DONE` with its valid Case D. T075 does not reinterpret or overwrite that result.

The accepted T065 run showed 107 replay-equivalent terminal source candidates crossing the frozen seed-group split boundary (`MAP_SCREEN=19`, `REWARDS=88`). Stage 0 replay/projection/restore fidelity passed. The replay identity is not being weakened or enriched: `public_state_identity` already contains the complete 4737-value public/model state, sanitized public run context, and ordered legal-action identities.

The only scientific change in T075 is therefore cohort partition order:

1. admit only strict-reader-valid terminal candidates from the four frozen mandatory families;
2. group all candidates from both retained source arms and all seed groups by the unchanged T065 replay-equivalence key;
3. choose one deterministic global owner per group using the unchanged T065 `(selection_digest, canonical_candidate_json_bytes)` order;
4. exclude all non-owners before quota selection;
5. retain the owner's original simulator-seed split;
6. within each `(family, split)` owner bucket, select the original frozen quota with the same deterministic ordering.

A replay-equivalent state can therefore appear in the raw source evidence more than once but can never survive into more than one split. If global ownership leaves any bucket below quota, T075 ends Case D. No source recollection, scale increase, split reassignment, balancing, target-aware selection, or replay-key change is allowed.

## Planner Baseline And Dependencies

Planner baseline:

`95ccb6b55bc7a0214b632206ae169a533289fcf2`

Required merged dependencies:

- T033 public-context model-input encoder contract;
- T040 `expert_non_combat_v1`;
- T061 reachability bottleneck evidence;
- T064 non-combat-learning recommendation;
- T065 learned non-combat workflow, model-input contract, retained Stage 1 evidence, and accepted Case-D report;
- T071 stage-local artifact reuse convention;
- T074 acyclic decision/policy ownership.

T034 remains out of scope. T063 and T066 remain `DRAFT` and are not authorized by T075.

## Frozen T065 Scientific Inputs

Except for cohort ownership/partition order, T075 reuses T065 unchanged.

### Source and simulator

- player class: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- controlled-run cap: `500`;
- Stage 1 source seeds: exactly `650001..650256`;
- source driver seed: exactly `654001`;
- source arms: `stochastic_non_combat_v1`, `expert_non_combat_v1`;
- battle controller: `OracleSearchController(simulations=20, root_selection_rule="highest_mean", action_space=ActionSpaceConfig.initial_no_potions())`;
- battle provenance name: `oracle_search_v1_highest_mean_s20`;
- original Stage 1 topology: 16 shards per arm, 16 seeds per shard, 16 effective workers.

T075 must reuse the exact retained Stage 1 files frozen in the linked execution/artifact contract. It may not invoke source collection. Missing, ambiguous, unreadable, hash-invalid, or provenance-invalid retained inputs are Case D at `source-input-reuse`.

### Seed-group split

The simulator-seed split remains:

- train: `650001..650154`;
- validation: `650155..650205`;
- heldout: `650206..650256`.

No simulator seed may change split.

### Mandatory families and quotas

Exactly:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas remain:

- train: 48;
- validation: 16;
- heldout: 16.

A valid selected cohort contains exactly 320 states.

`BOSS_RELIC_REWARDS`, shop, event, card-select, and unknown/unsupported screens remain fallback-only and are not selectable T075 training states.

### Candidate domain

Ownership admits only source-state rows that:

- pass the strict current `t065-source-state-v1` reader;
- belong to a source run with `terminal == true`;
- belong to one of the four mandatory families;
- retain the exact frozen simulator-seed split and source provenance;
- pass the existing T065 public/model/action/replay validation.

Nonterminal or truncated rows remain auditable source evidence but cannot become owners or selected states. Malformed/provenance-invalid rows fail closed rather than being silently filtered.

### Model input

Use `non-combat-model-input-v1` exactly:

- tactical snapshot: 4634;
- public context: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- no expert/behavior/hidden/future feature;
- normalization fit on training split only using CPU float32 population mean/std, `unbiased=False`, std clamped to at least 1.0, then checkpointed and reused unchanged.

### Counterfactual targets

Every selected state evaluates every eligible legal action from the same restored checkpoint.

Continuation driver remains `expert_non_combat_v1` with seeds:

- train: `(652001, 652002)`;
- validation: `(652101, 652102)`;
- heldout: `(652201, 652202, 652203, 652204)`.

Target remains:

`q_floor = mean(max(0, terminal_floor - source_floor))`

No action subsampling, replacement, alternate reward, or hidden-future resampling is allowed.

### Ranker

Model seeds: `(653001, 653002)`.

Topology:

```text
state 4737 -> Linear(4737,64) -> ReLU -> Linear(64,64) -> ReLU
action 92 -> Linear(92,64) -> ReLU -> Linear(64,64) -> ReLU
concat 128 -> Linear(128,64) -> ReLU -> Linear(64,1)
```

Training remains T065: CPU PyTorch, default `nn.Linear` initialization after `torch.manual_seed(model_seed)`, Huber delta 1, Adam lr `1e-3`, 1500 steps, 64 rows/step sampled with replacement by the frozen generator, gradient clip 10, `torch_threads=1`, no early stopping or architecture sweep. Validation `q_floor` MAE selects the checkpoint; exact tie chooses the lower model seed.

## Leakage-Safe Global Ownership

The replay-equivalence key remains exactly T065:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

The canonical candidate payload and selection key remain exactly T065:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

For each global replay group, sort members ascending by that pair. If the pair is unique, the first member is the sole owner and every other member is excluded before quota selection. The owner keeps the split implied by its simulator seed.

If two distinct source rows have an identical full pair, T075 fails closed as Case D at `cohort-ownership`; do not add another tie-break field. Exact group digest bytes, serialization, audit ordering, and required tied-row evidence are frozen in the linked normative contract.

After ownership, select the first 48/16/16 owners inside each family/split bucket using the same member order. No Act/floor balancing, arm quota, RNG, strategic-quality filter, target/model metric, manual substitution, or replacement is allowed.

## Leakage And Replay Gates

Before Stage 2, a valid cohort must have:

- exactly 48/16/16 states per family and 320 total;
- globally unique selected replay-equivalence keys;
- zero selected replay overlap across splits;
- zero simulator-seed split leakage;
- zero selected duplicate state;
- exact replay of every selected public/model state and ordered legal identities;
- zero replacement after replay failure.

Selected-state replay verification is a substantial simulator stage. Its exact 16-shard x 20-state topology, worker contract, commands, and evidence fields are frozen in the linked normative execution/artifact contract.

## Downstream Stages

If Stage 1 selection/replay is valid:

- Stage 2 generates all-action counterfactual targets using exactly 16 shards of 20 selected indices and at most 16 simulator workers;
- Stage 3 validates target completeness/model-input/lineage/firewall;
- Stage 4 trains exactly the two frozen model seeds;
- Stage 5 applies the unchanged held-out gate;
- Stage 6 runs only if Stage 5 passes.

Stage 5 uses the 64 held-out states and requires:

1. aggregate mean paired `q_floor(model)-q_floor(expert) > 0`;
2. median paired delta `>= 0`;
3. at least 3 of 4 family mean deltas `>= 0`;
4. 10,000-stratified-bootstrap `p_positive >= 0.90` using `random.Random(655001)`;
5. non-selected model seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violations.

A valid Stage 5 failure is Case C and skips Stage 6.

Conditional Stage 6 uses fresh seeds exactly `651001..651256`, driver/fallback seed `654002`, and three matched arms: stochastic, expert, learned-on-mandatory-families with expert fallback elsewhere. It remains 16 shards x 16 seeds per arm, at most 16 simulator workers, and requires 768 valid terminal runs. Bootstrap remains 10,000 matched-seed resamples with `random.Random(655002)`. Coverage remains `L/D >= 0.60`, `F/M <= 0.01`, with the exact T065 D/L/M/F definitions.

## Terminal Cases

T075 ends in exactly one case:

- Case A: valid repaired cohort, Stage 5 passes, Stage 6 passes; accept only an experimental public learned non-combat controller with fallback.
- Case B: Stage 5 passes but valid Stage 6 fails; no promotion.
- Case C: valid targets/cohort but Stage 5 fails; close this v1 target/model formulation and skip Stage 6.
- Case D: any retained-input, ownership, quota, replay, target, schema, leakage, simulator/provenance, truncation, or frozen-fidelity failure prevents attribution.

Cross-split replay groups before ownership are expected input. Cross-split replay overlap after ownership/selection is Case D.

## Engineering Boundary

Implementation, if independently authorized, must remain in the neutral owners:

- `src/sts_combat_rl/sim/non_combat_learning.py`;
- `src/sts_combat_rl/sim/non_combat_model_input.py`;
- `src/sts_combat_rl/commands/non_combat_learning.py` only for the neutral command surface frozen by the linked contract;
- focused tests in `tests/test_non_combat_learning.py`.

Do not create task-numbered production modules, add T075 flags/routes to the legacy flat CLI, alter the historical T065 result, recollect Stage 1, change replay/model identity, or perform unrelated cleanup/refactors.

## Required Verification And Evidence

The linked normative contract freezes:

- the isolated T075 code checkout/worktree and stable external artifact root;
- exact clean-branch/head checks and no-branch-switching rule;
- exact retained T065 inputs, accepted final Case-D evidence, path-normalization semantics, and retention/deletion rules;
- Stage 0/1/2/4/5/6 command templates;
- exact Stage 1 replay and downstream sharding/worker evidence;
- artifact schema ids/versions, parent hashes, ordering, required aggregate counts, stage command/evidence structures, and selected-state JSONL format;
- local/focused tests and standard project gates.

The implementation PR must report the exact approved T075 specification head, implementation head used for every scientific stage, retained source identities, ownership/group statistics, post-owner family/split availability, selection/replay evidence, all reached downstream metrics/costs, terminal Case A/B/C/D, and exactly one next recommendation.

## Lifecycle

T075 remains `DRAFT` until the Main Maintainer independently reviews the exact head and posts `SPEC APPROVED` with `implementation_authorized=true`.

The Planner does not implement or dispatch the task. This specification revision authorizes no source selection, target generation, training, or simulator evaluation by itself.
