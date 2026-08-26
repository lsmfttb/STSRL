# T065 Normative Frozen Execution And Statistics Contract

This file is a **normative part of the T065 specification** and must be reviewed
with `T065-learned-non-combat-policy-v1.md`. It freezes execution and statistical
inputs that the main task document previously described only at a higher level.
If wording in the main task document is more permissive than this file, this
file controls. Changing any item marked frozen below after specification
approval is a material specification change and requires Maintainer re-approval.

This contract does not authorize implementation. T065 remains `DRAFT` until the
Main Maintainer approves the exact proposal head.

## Frozen Simulator And Controller Configuration

All real simulator evidence uses the pinned current-main `sts_lightspeed`
integration and:

- player class: exactly `IRONCLAD`;
- ascension: exactly `20`;
- standard natural game start;
- maximum controlled-run simulator decision/step cap: exactly `500`;
- a run is terminal only when the authoritative simulator reports terminal at or
  before that cap;
- reaching the cap while non-terminal is an explicit truncation, never a
  terminal substitute;
- no replacement simulator seed is allowed for a truncated or failed required
  run;
- no HP, potion, encounter, route, restart, constructed-state, or other
  assistance is allowed unless already explicitly named as part of the frozen
  counterfactual branch operation;
- battle controller in Stage 1, Stage 2 continuations, and Stage 6 is exactly
  `OracleSearchController(simulations=20, root_selection_rule="highest_mean",
  action_space=ActionSpaceConfig.initial_no_potions())`;
- controller provenance name is exactly
  `oracle_search_v1_highest_mean_s20`;
- the frozen battle action-space dictionary is:

```json
{
  "excluded_kinds": [
    "game_potion_discard",
    "game_potion_use",
    "potion",
    "potion_discard",
    "reward_potion",
    "shop_reward_potion"
  ],
  "preferred_kinds": ["card", "end_turn"],
  "allow_excluded_fallback": true,
  "include_non_combat_potions": true
}
```

The exact Stage 1 source simulator seeds remain `650001..650256`. The exact
Stage 6 fresh simulator seeds remain `651001..651256` and are disjoint from
Stage 1.

## Frozen Non-Combat RNG Mapping

The stochastic and expert drivers already derive each run's RNG stream from the
pair `(driver_seed, simulator_seed)`. T065 freezes the driver seed separately
from the simulator seed so the Implementer cannot choose another behavior
randomization after seeing source coverage.

### Stage 1 source behavior

Use driver seed exactly `654001` for both source arms:

- `StochasticNonCombatDriver(seed=654001)`;
- `ExpertNonCombatDriver(seed=654001)`.

Before each source run, reset the selected driver for that run's source simulator
seed. Thus the two behavior arms share the same source simulator seed and the
same frozen driver-seed namespace while retaining their different policy logic.

### Stage 2 continuation behavior

The already frozen continuation-policy seeds are the **expert driver seeds**:

- training states: `(652001, 652002)`;
- validation states: `(652101, 652102)`;
- held-out states: `(652201, 652202, 652203, 652204)`.

For each candidate branch and each required continuation seed, construct/reset
`ExpertNonCombatDriver(seed=<continuation_seed>)` for the original source
simulator seed after restoring the exact source checkpoint and forcing the
candidate action. All candidate actions from one source state use the same
ordered continuation-seed tuple for that split. No continuation seed may be
replaced after a failure.

### Stage 6 complete-run behavior

Use driver seed exactly `654002` for every Stage 6 non-combat arm/fallback:

- stochastic baseline: `StochasticNonCombatDriver(seed=654002)`;
- expert baseline: `ExpertNonCombatDriver(seed=654002)`;
- learned arm expert fallback: `ExpertNonCombatDriver(seed=654002)`.

Reset the applicable driver for each Stage 6 simulator seed. Learned decisions
on mandatory supported screens are deterministic given the frozen checkpoint;
only the explicitly unsupported-screen fallback uses the expert RNG stream.

## Frozen Source Partition And Selection

T065 uses no selection RNG and no post-coverage discretionary stratification.
The previous wording that selection should or may preserve Act/floor diversity
is superseded by this deterministic contract.

### Seed-group split

The split is fixed before source collection:

- training seed groups: `650001..650154`;
- validation seed groups: `650155..650205`;
- held-out seed groups: `650206..650256`.

Both source behavior arms for one simulator seed inherit the same split. No
simulator seed can cross split boundaries.

The required selected-state counts remain, per mandatory screen family:

- training: 48;
- validation: 16;
- held-out: 16.

Mandatory family order is frozen as:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

`BOSS_RELIC_REWARDS` is **disabled as a T065 v1 learned/diagnostic family**. It
uses the normal expert fallback and does not enter the 320-state cohort. This
removes the prior optional-family discretion from T065.

### Candidate identity and deduplication

For every encountered mandatory-family decision from a terminal Stage 1 source
run, construct one canonical portable candidate identity from:

- screen family;
- simulator seed;
- source behavior arm;
- occurrence-disambiguated public action trace through that decision;
- source decision/step index;
- public-state identity/hash used by the portable replay contract;
- ordered legal-action identities.

Replay-equivalence across source arms is determined by the tuple:

`(screen_family, public_state_identity, ordered_legal_action_identities)`.

If multiple candidates are replay-equivalent, retain only the candidate with
the lexicographically smallest deterministic selection key below.

### Deterministic selection key

For each remaining candidate, serialize the canonical candidate identity as
UTF-8 canonical JSON using sorted keys and compact separators, then compute:

`sha256(b"T065-source-selection-v1\n" + canonical_json_bytes)`.

Within each `(screen_family, split)` bucket, sort ascending by the hexadecimal
SHA-256 digest; if two digests are identical, break the tie by the canonical
JSON bytes lexicographically. Select the first required 48/16/16 candidates.
There are no Act/floor quotas, balancing passes, manual substitutions, or
quality judgments.

The provisional selected 320 states are then replay-verified exactly. Any
selected state whose public state or ordered legal-action identity does not
replay exactly is a **Case D** failure; do not replace it with the next ranked
candidate after observing that failure.

If any mandatory `(family, split)` bucket cannot supply its frozen quota before
replay verification, T065 terminates as **Case D**. Do not increase source-run
scale or alter the selection rule inside T065.

## Frozen Stage 2 Target Completeness Rule

Order the 320 selected states globally by:

1. mandatory family order above;
2. split order `train`, `validation`, `heldout`;
3. deterministic selection rank within the `(family, split)` bucket.

Assign global selected-state indices `0..319` in that order.

Every selected state evaluates every eligible legal action and every required
continuation seed for its split. Missing branch rows, restore failures,
non-terminal continuation at the 500-step cap, controller errors, or target
non-finiteness make the frozen target dataset invalid and terminate T065 as
**Case D**. No candidate action, continuation seed, or selected source state may
be dropped or replaced to repair completeness after results are visible.

## Frozen Model Topology And Optimization

The two model seeds remain exactly `(653001, 653002)`.

The action-conditioned ranker topology is exactly:

```text
state features (dimension d_state)
  -> Linear(d_state, 64)
  -> ReLU
  -> Linear(64, 64)
  -> ReLU

public action features (dimension d_action)
  -> Linear(d_action, 64)
  -> ReLU
  -> Linear(64, 64)
  -> ReLU

concatenate -> 128 features
  -> Linear(128, 64)
  -> ReLU
  -> Linear(64, 1)
  -> unrestricted scalar q_floor prediction
```

There is no dropout, batch normalization, residual connection, attention,
ensemble averaging, output activation, or learned expert prior. The state and
action feature dimensions come only from the versioned
`non_combat_model_input_v1` public-input schema required by the main task; that
schema must be identical for training, validation, held-out scoring, and online
Stage 6 control.

Optimization is frozen as:

- framework: PyTorch CPU;
- call `torch.manual_seed(model_seed)` before constructing the model;
- `nn.Linear` uses the PyTorch default initialization from that seeded state;
- loss: `HuberLoss(delta=1.0, reduction="mean")`;
- optimizer: `Adam(lr=1e-3, betas=(0.9, 0.999), eps=1e-8,
  weight_decay=0, amsgrad=False)`;
- no learning-rate scheduler;
- exactly 1500 optimizer steps;
- exactly 64 candidate-action rows per optimizer step;
- gradient clip norm exactly 10;
- `torch_threads=1` per model run;
- no early stopping or checkpoint averaging.

Training minibatch sampling is also frozen. For one model seed, create a CPU
`torch.Generator` with seed `model_seed + 1_000_000`. At every optimizer step,
sample 64 row indices **with replacement** from the complete training
candidate-action table using `torch.randint(0, N, (64,), generator=generator)`.
The candidate-action table order is deterministic from the selected-state order,
then legal-action order. Validation and held-out metrics score their complete
frozen tables; they do not subsample rows.

Checkpoint selection remains lower validation `q_floor` MAE, with exact ties
broken by the lower model seed.

## Frozen Bootstrap Procedures

Bootstrap probabilities use no confidence-interval interpolation, no
pseudocount, and no adaptive resampling count.

### Stage 5 held-out gate

- replicates: exactly `10,000`;
- RNG: Python `random.Random(655001)`;
- resampling unit: source state;
- stratification: mandatory screen family;
- each replicate independently samples 16 held-out states with replacement from
  each of the four mandatory families, giving 64 sampled state deltas;
- statistic: arithmetic mean of the 64 paired empirical
  `q_floor(model_selected) - q_floor(expert_selected)` deltas;
- probability estimate:
  `p_positive = count(replicate_mean > 0.0) / 10000`.

The existing Stage 5 threshold is applied exactly to this probability:
`p_positive >= 0.90`. Aggregate mean, median, per-family means, and the second
model-seed condition use the original 64-state cohort, not bootstrap resamples.
A missing or non-finite paired delta is Case D before bootstrap calculation.

### Stage 6 complete-run gate

- replicates: exactly `10,000`;
- RNG: Python `random.Random(655002)`;
- resampling unit: matched Stage 6 simulator seed;
- each replicate samples 256 seed indices with replacement from the complete
  learned-vs-expert paired cohort;
- statistic: arithmetic mean of the sampled paired terminal-floor deltas;
- probability estimate:
  `p_positive = count(replicate_mean > 0.0) / 10000`.

The existing complete-run thresholds apply exactly to this probability:
`>= 0.80` for the ordinary probability condition and `>= 0.95` for the stronger
signal alternative. Missing, truncated, errored, or non-finite required paired
runs invalidate the scientific comparison and produce Case D rather than being
removed from the bootstrap cohort.

## Frozen WSL Shard Topology

The host target is at most 16 concurrent simulator workers. Deterministic merge,
manifest, training-summary, and report aggregation may be single-process because
they do not advance the simulator.

### Stage 1 source collection

For each of the two source behavior arms, use exactly 16 shards. Shard `k` for
`k=0..15` owns exactly these 16 source simulator seeds:

`650001 + 16*k .. 650016 + 16*k`.

This produces 32 source-collection jobs total, with at most 16 jobs concurrent.
Each job uses the frozen arm policy, `driver_seed=654001`, A20 IRONCLAD, step cap
500, and the frozen battle controller/action space.

### Stage 2 replay verification and target generation

Use exactly 16 shards over the globally indexed 320-state selected cohort.
Shard `k` owns selected-state indices:

`20*k .. 20*k + 19`.

Each shard owns **all** candidate actions and all required continuation seeds for
its 20 states. Candidate actions or continuation seeds must not be split across
another shard. Run at most 16 Stage 2 shards concurrently.

### Stage 4 training

Training is not a WSL simulator stage. The two frozen model-seed runs may execute
concurrently with at most two model processes and `torch_threads=1` in each.

### Stage 5 held-out aggregation

No simulator sharding is required because Stage 5 reads the complete frozen
held-out target table and model checkpoints.

### Stage 6 complete-run evaluation

For each of the three Stage 6 arms, use exactly 16 shards. Shard `k` for
`k=0..15` owns exactly these 16 fresh simulator seeds:

`651001 + 16*k .. 651016 + 16*k`.

This produces 48 Stage 6 simulator jobs total, with at most 16 jobs concurrent.
All three arms must eventually contain all 256 frozen seeds. The stochastic,
expert, and learned/fallback arms use the same seed partition and the frozen
`driver_seed=654002` mapping.

## Frozen Stage 6 Learned-Control Coverage Formula

Coverage is computed only on the learned arm after all required Stage 6 runs
have valid terminal records. A required run truncation, controller error,
illegal action, or missing decision record is Case D; coverage numbers may be
reported diagnostically but cannot rescue an invalid comparison.

Let:

- `D` = the number of **all non-battle decision contexts** encountered across
  the 256 learned-arm runs, including both mandatory supported screens and
  intentional unsupported-screen fallback decisions;
- `L` = the number of those decisions whose screen is one of the four mandatory
  families and for which `learned_non_combat_v1` successfully encoded the
  context, scored the complete eligible legal-action set, and supplied the
  accepted action without fallback;
- `M` = the number of learned-arm decisions whose screen is one of the four
  mandatory families;
- `F` = the number of those `M` mandatory-family decisions where learned control
  failed because of schema, encoder, model-inference, or supported-action
  coverage failure and therefore produced a named fallback/error instead of a
  normal learned selection.

Then:

- learned-control coverage is exactly `L / D` and must be `>= 0.60`;
- mandatory-family supported-failure rate is exactly `F / M` and must be
  `<= 0.01`;
- if `D == 0` or `M == 0`, Stage 6 is Case D;
- intentional unsupported-screen fallback contributes to `D` but not `L` and
  does not contribute to `F`;
- a successful learned decision contributes to `D`, `L`, and `M`;
- a mandatory-family learned failure contributes to `D`, `M`, and `F`, but not
  `L`;
- battle decisions contribute to none of `D/L/M/F`;
- truncation/controller/illegal-action failures are not removed from a
  denominator; they invalidate Stage 6 as Case D before promotion-gate
  interpretation.

No screen/action category may be reclassified from mandatory to unsupported
after Stage 6 results are observed.

## Frozen Early-Failure Case D Semantics

Case D explicitly includes all of these early paths:

- any mandatory `(family, split)` has fewer candidates than its frozen quota;
- any one of the 320 selected states fails exact replay/public-state/legal-action
  equality;
- any Stage 1 required source run truncates or fails;
- any selected candidate action or continuation seed is missing, truncated,
  non-finite, or fails restore/controller execution;
- split leakage or replay-equivalent cross-split duplication is detected;
- hidden/private information enters deployable model input;
- any other frozen fidelity/completeness condition prevents valid attribution.

For a Case D triggered before training, do not train models or run Stage 5/6.
For a Case D triggered during/after a later stage, do not execute any subsequent
scientific stage.

A valid Case D implementation report must still contain:

- the exact approved specification head and simulator/source identity;
- all successfully completed preceding-stage manifests;
- the exact failing family/split/state/branch/run identities and counts;
- explicit confirmation that no replacement seed/state/action/continuation was
  substituted and no source scale was increased;
- skipped downstream stages;
- one narrow repair recommendation only;
- no policy-improvement conclusion.

Normal acceptance requirements that mathematically require downstream artifacts
(for example exactly 320 replay-valid states, trained checkpoints, or 768 Stage
6 runs) are **conditional on reaching those stages**. A correctly detected and
reported Case D may close T065 as an invalid-experiment diagnostic without
pretending that downstream scientific acceptance gates passed. It cannot promote
a controller or authorize larger scale.

## No Remaining Implementer Choice Over Scientific Inputs

The Implementer may choose ordinary internal function/file organization,
logging layout, and efficient equivalent mechanics for realizing this exact
contract. The Implementer may not choose or tune simulator seeds, driver seeds,
step cap, character, cohort-selection/split rules, optional learned families,
continuation replication, model topology, optimizer settings, minibatch RNG,
bootstrap procedure, shard partition, gate formula, or terminal-case mapping.

Any discovered incompatibility that would require changing one of those frozen
items must stop before the affected expensive stage and return to specification
review rather than being repaired post hoc inside the implementation.