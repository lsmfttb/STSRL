# First Battle Trainer Plan

> Historical document. This records the initial trainer spike and is not the
> current roadmap. See `docs/current_status.md` and
> `docs/battle_dataset_search_and_sl_plan.md`.

This document defines the narrow starting line and next roadmap for battle-only
RL training. The current phase allows small pure-Python battle-agent training
spikes and optional PyTorch policy/value models, while still avoiding Gymnasium,
Stable-Baselines3, and local game-mechanics implementations.

The detailed current roadmap for battle-start checkpoints, structurally
stratified datasets, search-agent development, and the separate SL-enabled agent
branch is in `docs/battle_dataset_search_and_sl_plan.md`. That roadmap takes
precedence over older experimental directions in this document.
The normal-information search, Oracle-transfer, and terminal resource-value
architecture is defined in
`docs/normal_information_search_and_resource_value_plan.md`.
Repository-wide implementation boundaries and coding principles are defined in
`docs/project_architecture.md`.

## Scope

The first trainable target is Ironclad battle decisions only.

- The battle agent chooses only in `BATTLE` states.
- Non-combat decisions stay under the separate non-combat driver.
- The legacy smoke action space excludes potion-related actions by default.
  Serious training may include battle potions after the terminal resource
  contract preserves potion identities and continuation value.
- `battle-v0` remains the initial reward preset.
- The final target is A20. A0 is only an early curriculum stage; ascension is
  explicit state input because combat transitions can differ by ascension.
- Long-term resources remain separate structured targets until a learned
  continuation value can price them in context.

## Agreed Training Direction

- Human battle data is optional and expected to remain small.
- Treat simulator search as the primary battle policy. A PyTorch policy/value
  model may guide branch ordering, leaf evaluation, rollouts, or search-budget
  allocation, but is not expected to replace search at inference time.
- Evaluate learned models by whether they improve search strength or reduce the
  compute needed for the same strength. Raw neural-policy strength is a
  diagnostic metric, not the primary success gate.
- The first no-potion battle objective is battle result plus terminal absolute
  current HP. Do not normalize this HP target by max HP: `40/80` is worse than
  `60/120` despite the equal ratio.
- Turn/decision count has zero default reward weight.
- Potion use, relic-counter setup, gold, max HP, and persistent deck changes
  enter the planned terminal resource outcome vector. They must not be reduced
  permanently to fixed hand-written reward weights.
- PyTorch is allowed. Gymnasium and Stable-Baselines3 remain deferred.

## Search Teacher Gate

The first AlphaZero-like prerequisite is now available: patched
`sts_lightspeed` can search copied battle states and return a root visit
distribution aligned with the current legal actions.

Run the reusable search-teacher smoke in WSL:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-search-smoke --sim-seed 1 --sim-ascension 0 --sim-steps 200 --search-simulations 100"
```

The required result is:

```text
search target ready: yes
problems:
  (none)
```

Run the same gate with `--sim-ascension 20` before treating a search-interface
change as A20-compatible. The search teacher preserves every actual legal root
action, while deeper search nodes may still merge equivalent duplicate cards
for efficiency.

The current searcher still uses its built-in random terminal-rollout evaluator
and sees hidden simulator RNG. It is an Oracle-like smoke baseline, not the
target normal-information teacher. Root visits are also influenced by UCB
exploration, so low-budget visits must not be assumed to be the best played
action. Preserve visits as audit data, but do not scale serious training by
simply increasing this rollout count.

## Search Dataset And PyTorch Warmup

The search JSONL and PyTorch pipeline below remains useful infrastructure, but
large-scale collection should now wait for the battle-start checkpoint and
stratified-evaluation gates defined in
`docs/battle_dataset_search_and_sl_plan.md`.

Collect several consecutive search-controlled battles per seed:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-final:/mnt/d/DeadlycatCoding/STSRL/src /home/lsmft/stsrl-spikes/py313-torch/bin/python -m sts_combat_rl.cli --lightspeed-battle-search-dataset-jsonl artifacts/search_training/train_a20_s100.jsonl --sim-seed 1 --sim-ascension 20 --sim-episodes 10 --sim-steps 200 --search-battles-per-seed 10 --search-simulations 100 --search-selection-rule highest-mean"
```

Each decision record contains:

- the selected search action as the default one-hot policy target;
- the full root visit distribution as separate audit/optional soft-label data;
- the actual behavior action when collecting DAgger model trajectories;
- `outcome_target`: battle win `+1`, death `-1`;
- `terminal_current_hp_target`: absolute current HP after that battle;
- `terminal_max_hp_audit`: audit metadata only, never the HP target denominator.
- `terminal_resource_target`: separate numeric resource components for model
  prediction;
- `terminal_resource_outcome`: structured potion, deck/curse, relic, key,
  HP/max-HP, and gold changes for audit and later continuation-value work.

Search datasets, natural battle-start pools, and fixed evaluation cohorts must
record complete controller provenance. A short label such as `preferred-kind`
or `highest-mean` is not sufficient to reproduce collection; search budget,
selection rule, action space, behavior policy, and non-combat driver must remain
explicit.

New search-training exports use format v3. Historical v1/v2 files remain
readable, but missing teacher/behavior/non-combat provenance and terminal
resource labels are recorded as explicit migration losses. Legacy controllers
remain explicitly non-reproducible. Use
`--artifact-migrate search-training OLD.jsonl NEW.jsonl` to rewrite them while
preserving migration lineage.

Train the optional PyTorch cross-interaction policy/value network on Windows:

```text
python -m sts_combat_rl.cli --search-dataset-train-torch artifacts/search_training/train_a20_s100.jsonl artifacts/search_training/dagger_a20.jsonl --torch-policy-target-override root_visit_distribution --torch-output-model artifacts/models/policy_a20.pt --torch-epochs 100 --torch-hidden-size 128 --torch-batch-size 32 --torch-policy-loss-weight 1 --torch-outcome-loss-weight 0 --torch-hp-loss-weight 0
```

Evaluate a saved checkpoint on held-out seeds:

```text
python -m sts_combat_rl.cli --search-dataset-eval-torch artifacts/search_training/heldout_multibattle_a0_seed2_b10_s20.jsonl artifacts/search_training/heldout_multibattle_a20_seed2_b10_s20.jsonl --torch-model artifacts/models/policy_value_multibattle_train_seed1_3_5.pt
```

The policy head scores explicit
`[state_embedding, action_embedding, state_embedding * action_embedding]`
cross features. The value side has separate outcome, absolute-current-HP, and
terminal-resource-vector heads. `--torch-hp-loss-scale` and the fixed
per-resource scales are optimization conditioning only, not max-HP
normalization or fixed resource reward weights. Current PyTorch checkpoint
format v3 adds the resource head; v1/v2 checkpoints remain loadable through
explicit migrations.

For WSL online inference, use:

```text
PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-final:/mnt/d/DeadlycatCoding/STSRL/src /home/lsmft/stsrl-spikes/py313-torch/bin/python -m sts_combat_rl.cli --lightspeed-battle-torch-model-eval artifacts/models/policy_value_multibattle_train_seed1_3_5.pt --sim-seed 1 --sim-ascension 20 --sim-episodes 10 --sim-steps 200
```

Current calibration results:

- A20 seeds 1-10 fixed `preferred-kind` baseline: average floor `7.7`;
- A20 20-simulation `highest-mean` direct search: average floor `8.1`;
- A20 100-simulation `highest-mean` direct search: average floor `8.0`;
- the best compressed A20 soft-root-visit model matched the fixed baseline at
  average floor `7.7`;
- hard one-hot labels overfit, while repeated DAgger, simple model ensembles,
  and action-kind-prior blending did not beat the A20 model gate.

The current stochastic-driver A20 seeds 101-200 pool passes 487/487 portable
checkpoint restores, and its 56-battle fixed cohort establishes the primary
20-simulation search baseline. The remaining bottlenecks are Boss/later-act
state generation and search quality, especially the 0/9 Act 1 elite result on
this deliberately diverse incoming-state cohort. Do not prioritize raw-policy
compression or assume additional same-style DAgger rounds or 500-simulation
labels will improve the primary search agent without fixed
encounter-stratified evidence.

## Required Gate

Before starting a trainer run, the WSL `sts_lightspeed` readiness gate must pass:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-training-readiness --sim-seed 1 --sim-episodes 10 --sim-steps 200"
```

The required result is:

```text
trainer interface ready: yes
problems:
  (none)
```

This gate verifies battle examples, reward-label alignment, trainer input JSONL
round-trip, flattened model input packing, context rebuild, and one-score-per
legal-action-row scoring.

## Dataset Export

Export a reproducible trainer input dataset after readiness passes:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-trainer-input-jsonl artifacts/trainer_input/battle_seed1_e10_s200.jsonl --sim-seed 1 --sim-episodes 10 --sim-steps 200"
```

The JSONL metadata records the data-generation command parameters:

- simulator source and adapter;
- seed range, ascension, episode count, and step limit;
- battle policy and non-combat driver;
- reward preset;
- potion inclusion flag and action-space configuration.

New trainer-input exports use format v2 and include complete battle/non-combat
controller provenance. Historical v1 exports remain readable through the shared
migration layer; because they recorded only short policy names, migrated v1
controllers are explicitly marked non-reproducible. Use
`--artifact-migrate trainer-input OLD.jsonl NEW.jsonl` to rewrite them while
preserving migration lineage.

The output is ignored by git under `artifacts/`.

## Offline Dataset Preflight

Before a trainer imports the exported JSONL, run the offline preflight:

```text
python -m sts_combat_rl.cli --trainer-input-preflight artifacts/trainer_input/battle_seed1_e10_s200.jsonl
```

The required result is:

```text
preflight ok: yes
problems:
  (none)
```

This command does not require `sts_lightspeed` after export. It reads the JSONL,
validates the loaded dataset, packs flattened variable-action model input rows,
rebuilds scorer contexts, and checks that the deterministic smoke scorer emits
one finite score per legal action row.

## First Offline Training Warmup

The first training command is an offline behavior-cloning smoke, not an RL run:

```text
python -m sts_combat_rl.cli --trainer-input-train-linear artifacts/trainer_input/battle_seed1_e10_s200.jsonl --trainer-output-model-json artifacts/models/linear_action_seed1_e10_s200.json --trainer-epochs 5 --trainer-learning-rate 0.05
```

The required result is:

```text
training ok: yes
problems:
  (none)
```

This learns a small linear state/action scorer from the collected chosen
actions, then evaluates it through the same eligible-action argmax contract used
by the model-score smoke. The JSON model stores action weights, state-action
interaction weights, and metadata; it should stay under ignored `artifacts/`.

Reload the saved model and score the exported dataset with:

```text
python -m sts_combat_rl.cli --trainer-input-score-linear artifacts/trainer_input/battle_seed1_e10_s200.jsonl --trainer-model-json artifacts/models/linear_action_seed1_e10_s200.json --reward-detail-limit 0
```

This is the first persistence check for a learned scorer: saved JSON weights must
load back into the same `BatchActionScorer` boundary and produce one finite score
per legal action row.

Evaluate the saved scorer online through WSL `sts_lightspeed` with:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-linear-model-eval artifacts/models/linear_action_seed1_e10_s200.json --sim-seed 1 --sim-episodes 10 --sim-steps 200"
```

This verifies the saved scorer can drive actual simulator battle decisions while
non-combat states remain under the separate driver.

Compare it against the fixed baselines on the same seed range with:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-policy-compare artifacts/models/linear_action_seed1_e10_s200.json --sim-seed 1 --sim-episodes 10 --sim-steps 200"
```

This comparison panel is the standard pre-RL evaluation surface. Any later
policy-improvement experiment should beat or at least match these baselines
without introducing illegal-action problems.

## First Policy-Gradient Spike

Run the first minimal battle-only REINFORCE experiment from the saved linear
scorer with:

```text
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-reinforce artifacts/models/linear_action_seed1_e10_s200.json --rl-output-model-json artifacts/models/reinforce_linear_action_seed1.json --rl-iterations 3 --sim-seed 1 --sim-episodes 3 --sim-steps 200 --rl-learning-rate 0.01 --rl-temperature 1.0"
```

This is the first true policy-improvement loop in the repo, but it remains
intentionally small:

- the policy is still a pure-Python linear scorer over tactical action features
  and compact state-action interactions;
- actions are sampled with a softmax over eligible legal actions;
- `battle-v0` segment returns weight the log-probability gradient;
- non-combat states stay under the separate driver;
- no Gymnasium, Stable-Baselines3, deep-learning framework, or local game
  mechanics are introduced.

After writing `reinforce_linear_action_seed1.json`, run the same comparison
panel against that model before treating it as progress.

## Feature And Model Roadmap

The current scorer is useful as a pipeline test but is not expressive enough to
be a strong combat policy. Progress should happen in this order.

### Phase 1: Tactical Battle Features

Upgrade features that directly affect immediate combat choices:

- monster identity: `id`/name category, boss/elite/minion tags where available;
- monster intent and move state: intent category, `move_id`, `last_move_id`,
  `second_last_move_id`, attack damage, hit count, targetability, half-dead
  state, and key powers;
- card-action details: selected hand index, card id/category, type, cost,
  upgrade count, playable flag, target requirement, exhaust/ethereal flags;
- target-action details: selected monster index, target monster identity, hp,
  block, intent, powers, and lethal/overkill-style derived flags when the raw
  fields support them.

This phase should remain battle-only and should not require a neural framework.

Current implementation note: the first tactical upgrade is in place. The
encoder currently emits 813 battle snapshot features and 159 legal-action
features, including hashed card/monster/potion identity buckets, monster
intent/move buckets, selected-card context, selected-target context, and simple
energy/target/incoming-damage action context. Ascension is an explicit snapshot
feature so A0 and A20 are not treated as the same transition model.

### Phase 2: State-Conditional Scoring

Replace the action-only linear scorer with `score(state, action)`. The first
pure-Python version is now in place: `LinearActionScorer` supports action
weights plus state-action interaction weights over the first 32 snapshot
features and every action feature, so the same action can score differently
across battle states.

Candidate approaches:

- explicit state-action interaction features for important tactical products;
- a bilinear or low-rank interaction model over selected state/action feature
  groups;
- later, a small state encoder plus action encoder when adding a neural
  framework becomes worthwhile.

Do not rely on a pure two-tower dot product as the only scorer. It is useful for
retrieval-style ranking, but combat decisions need cross information such as
"this attack into this monster while that monster is attacking." Preserve those
interactions with explicit cross features, bilinear terms, concatenated
`[state_embedding, action_embedding, state_embedding * action_embedding]`
features, or an attention-style entity model when the project reaches a neural
implementation.

The action is not a second copy of the state. It is the candidate intervention
being evaluated under that state. The model should answer: "given this battle
state, what is the value of choosing this specific legal action now?"

### Phase 3: Deck And Relic Context Features

Add higher-level run context after immediate tactical features are stable:

- deck composition summaries: attack/defense/scaling/draw/exhaust/power/card
  counts, average cost, upgraded ratio, curse/status burden;
- energy and draw balance: expected playable cards, draw density, energy gain,
  hand-size pressure, discard/exhaust recursion indicators;
- defensive capacity: block density, weak/frail mitigation, sustain, artifact,
  intangible/buffer-like effects if visible;
- scaling and boss-readiness proxies: strength/dexterity scaling, AoE, single
  target damage, frontload versus scaling balance;
- relic context: relic id/category features and derived effects that materially
  alter combat evaluation when they are visible from the adapter.

These features are higher-dimensional and may need careful aggregation rather
than one-hotting every card/relic immediately. They belong before long-term
map/reward/shop learning, because battle choices already depend on deck and
relic context.

### Phase 4: Search Improvement And Optional Learned Guidance

The search-teacher and PyTorch interfaces are ready, but the primary goal is now
to improve the search agent:

- build fixed encounter-stratified evaluation from restorable battle-start
  checkpoints;
- compare search variants under equal simulation and wall-clock budgets;
- use learned policy/value models only as explicit search priors, leaf
  evaluators, rollout policies, or uncertainty estimators;
- require a search-only control for every learned-guidance experiment;
- retain variable legal-action scoring and eligible-action filtering as the
  policy boundary;
- keep the normal-information agent separate from the planned SL-enabled
  restart/oracle branch;
- enforce a public-information firewall and build a public policy/vector-value
  baseline before normal belief search;
- use Oracle search only for upper bounds, search-engine development, and
  same-public-state multi-future auxiliary targets;
- do not add Gymnasium/SB3 until the custom battle-agent interface has clear
  metrics and failure modes.

## Trainer Input Contract

Each trainer record contains:

- `snapshot_features`: fixed-size battle-state features, currently 813 values;
- `legal_action_features`: variable-length candidate action rows, currently 159
  values per action;
- `eligible_action_indices`: legal-action indices allowed by the active
  first-pass action-space config;
- `chosen_action_index` and `chosen_action_kind`: collector choice metadata;
- `step_reward`, `return_to_go`, segment metadata, and raw reward components.

The first model boundary should consume flattened variable-action rows, not a
fixed global action mask. For each decision example, score every legal action row
and choose the highest-scored eligible action.

## First Training Spike

The first trainer starts as a small offline experiment around the existing
model-input contract:

- Load `TrainerInputDataset` from JSONL.
- Build `ModelInputBatch`.
- Train a minimal state/action scorer against the current battle-only collected
  action labels.
- Save and reload the scorer as a small JSON model.
- Score the exported dataset with the reloaded scorer.
- Run a WSL battle sweep with the reloaded scorer controlling battle states.
- Run the same-seed WSL baseline comparison panel.
- Run the minimal WSL REINFORCE spike and compare the updated model.
- Report agreement with collected actions and policy episode evaluation against
  baseline policies.

Do not introduce Gymnasium, Stable-Baselines3, potion control, map/reward/shop
learning, or local Slay the Spire mechanics in this first spike.

## Starting Baselines

Compare any first trained policy against:

- `preferred-kind`;
- `first-eligible`;
- `random-eligible`;
- `action-kind-prior-scorer`.

The first useful training result is not a high win rate. It is a verified loop
where a learned scorer can be loaded, choose only eligible battle actions, run
through WSL `sts_lightspeed`, and report metrics without breaking the current
CommunicationMod probe or trainer input contracts.
