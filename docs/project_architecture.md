# Project Architecture

This is the authoritative repository-wide design contract. Active roadmaps may
add capabilities, but they must preserve these boundaries unless this document
is deliberately revised.

## Objective And Scope

The final objective is A20 Heart victory probability.

The current trainable scope is battle decisions. A separately named non-combat
driver advances complete runs and generates battle-start distributions. The
driver is not yet a learned long-term policy, but its behavior and provenance
matter because it determines which battle states are reached.

Search is the primary battle-policy direction. Learned policies and values are
evaluated mainly as search guidance or acceleration. Standalone neural-policy
strength remains a diagnostic.

## Simulator Boundary

`sts_lightspeed` is the authoritative game implementation. This repository may:

- select legal actions;
- search copied simulator states;
- encode player-visible observations;
- collect and migrate datasets;
- train models;
- evaluate controllers.

It must not reimplement Slay the Spire mechanics. Authoritative state mutation,
legal-action enumeration, battle-start restore, encounter selection, and hidden
future sampling must come from the simulator.

Real `sts_lightspeed` gates run through WSL. Game files, simulator binaries,
save files, and large artifacts do not belong in this repository.

## Information Regimes

Every controller, dataset, checkpoint, and evaluation report declares its
information regime.

### `normal_public_policy`

A policy or value model acts from player-visible state and public history only.

### `normal_belief_search`

Search reasons over simulator-sampled hidden futures consistent with the same
public state and history.

### `full_simulator_state_oracle_like`

Search copies the actual hidden simulator state. Current native
`BattleScumSearcher2` belongs here.

### `sl_attempt_budgeted`

The agent may restart a battle a named number of times and retain observations
between attempts. This is a separate project branch and evaluation regime.

Normal-information paths must not receive hidden RNG, unrevealed future
encounters, hidden draw order, or the hidden Act-3 second Boss. Oracle data may
support diagnostics or auxiliary learning, but it must never be silently
reported as normal-information performance.

## Public Decision State

A tactical battle snapshot is insufficient once battle actions preserve
resources for later rooms. The long-term public state target is:

```text
public tactical battle state
+ persistent public run resources
+ complete player-visible run history
+ complete visible map and available routes
+ visible Act Boss
```

Complete player-visible history includes all public facts that may change the
continuation distribution or value:

- visited rooms and route;
- battles and public outcomes;
- events seen, choices made, and public results;
- rewards, skips, card removals, shops, rests, relic choices, potion choices,
  keys, and other visible decisions;
- any public state needed to determine whether future content can still occur.

The history must be typed and versioned rather than stored only as prose or an
unstructured action trace. Missing fields remain explicit. Public context is
sanitized before it reaches normal controllers or model-input packing.

The current implementation carries only part of this target, mainly encounter
history and visible route context. That limitation belongs in
`current_status.md`; it does not narrow the architectural target.

## Dependency Direction

```text
simulator contracts, public decision context, controller contract
    -> concrete policy/search/model controllers
    -> controlled-run executor
    -> observers, datasets, training, and evaluation
    -> command handlers
    -> CLI parsing and routing
```

Lower layers do not import command handlers or the CLI. Dataset helpers do not
construct hidden default controllers.

## Online Control And State Advancement

Every action selector implements the explicit `OnlineController` contract and
publishes complete `ControllerProvenance`.

- `PolicyController` adapts a framework-neutral policy or learned scorer.
- `OracleSearchController` wraps current hidden-state native search.
- future normal search uses a separately named controller;
- `RoutedRunController` explicitly routes battle and non-combat decisions.

`execute_controlled_run` is the authoritative complete-run advancement path. It
centralizes decision-context construction, action-space filtering, controller
invocation, selected-index validation, transitions, and observers.

Specialized loops are allowed only for a genuinely different boundary:

- replaying a trace to restore a checkpoint;
- validating checkpoint determinism;
- playing one restored battle for fixed evaluation;
- collecting search labels and terminal targets.

They reuse shared controller selection and validation semantics. They do not
silently choose a policy or redefine root action selection.

## Non-Combat Driver

Natural-run drivers remain seeded and stochastic. Priors change hierarchical
category probabilities; they do not replace natural collection with a
deterministic hand-written route.

Low-probability legal branches remain reachable, including:

- taking or skipping ordinary and Boss relics;
- opening or leaving treasure;
- using non-combat potions;
- discarding potions before replacements;
- taking keys and other Heart-related branches.

Battle-only action exclusions do not remove non-combat branches. Behavior
changes require a new versioned driver name and complete provenance.

## Dataset Distributions

Keep these distributions separate:

1. **Natural run:** complete runs under named battle and non-combat controllers.
2. **Stratified training:** reported resampling of natural checkpoints by
   structural metadata.
3. **Constructed supplement:** explicitly modified authoritative battle starts.
4. **Paired counterfactual evaluation:** the same source state compared under
   controlled alternatives.

Also keep normal-information, Oracle-like, and SL-enabled information regimes
separate within those distributions.

Structural strata may use rule-defined metadata such as ascension, act, room
type, encounter id, floor bucket, or observed resource bucket. Do not filter
states using hand-written judgments about whether a deck, relic set, or route
is strategically reasonable.

Stratified resampling changes optimization weight. It does not create new
unique-state coverage. Preserve the source checkpoint and sampling component on
every decision.

Coverage reports distinguish:

- battle-start checkpoints;
- unique source battle starts;
- battle wins;
- later-act progression;
- natural-weighted, encounter-macro, and room-type-macro results.

Coverage and broad-training readiness are checked separately per ascension and
act. A0 data cannot hide missing A20 coverage.

## Constructed Battle Starts

Constructed states are supplemental data, never natural A20 evaluation
evidence. Every transform preserves:

- source checkpoint and source distribution;
- same ascension and ruleset;
- versioned seeded proposal policy;
- eligibility and trigger decisions;
- requested and actual changes.

Only actual changes receive a constructed-data tag.

HP augmentation should use a practical conservative approximation rather than
requiring expensive downstream replay for every small perturbation. The policy
must cap changes using observable opportunity and plausibility signals, favor
small deltas, avoid impossible early-run states, remain stochastic, and report
its assumptions. Authoritative replay is useful for audits and high-impact
transforms, but is not mandatory.

Potion additions and encounter replacements follow the same conservative,
explicitly tagged principle. Visible-Boss replacement remains
paired-counterfactual evaluation only because earlier route and resource
decisions were conditioned on the known Boss. Cross-ascension A0-to-A20
reconstruction is excluded from A20 training and evaluation.

## Objective And Labels

Battle death has zero continuation value. Battle survival, absolute current HP,
potion inventory, gold, max HP, persistent deck changes, curses, relic
counters, and other resources are intermediate outcomes whose value depends on
the complete public continuation state.

Persist:

- battle outcome;
- terminal absolute current HP, never normalized by max HP;
- structured terminal resource outcomes;
- later run outcomes and continuation-controller provenance when available.

Do not permanently collapse resources into fixed hand-written reward weights.
Component heads and reports remain independently auditable even after a learned
continuation value exists.

## Search And Model Evaluation

Current random terminal-rollout count is a smoke/Oracle budget, not a plan to
enumerate the battle state space. Serious search development uses public policy
priors, learned leaf values, uncertainty-aware allocation, and belief-state
handling.

Search comparisons report simulation count, model calls, simulator steps,
wall-clock time, and fixed-cohort results. Learned models are promoted only when
they improve credible held-out or fixed evaluation, not merely training fit or
one small average-floor measurement.

## Provenance And Artifact Versioning

Every persisted dataset and evaluation cohort records all behavior-changing
configuration:

- controller kind, implementation, and information regime;
- search budget and root-selection rule;
- action-space exclusions;
- model/checkpoint identity;
- non-combat driver and stochastic configuration;
- seed, ascension, and distribution kind.

A short policy name is not sufficient provenance.

Writers emit only current schemas. Readers migrate legacy artifacts before
business logic runs:

```text
raw versioned artifact
    -> version-specific parser
    -> sequential migrations vN -> vN+1
    -> current in-memory schema
    -> current-schema validation
```

Migrations report information that cannot be recovered and never guess missing
provenance. Portable replay traces identify both public action id and duplicate
occurrence. Legacy fixtures and migration regression tests remain in the
repository.

## Code Ownership

- `cli.py` owns argument definitions, cross-command validation, and routing.
- `src/sts_combat_rl/commands/` owns workflows.
- reusable simulator, controller, dataset, model, and evaluation logic lives
  below the command layer.
- CommunicationMod formatting stays centralized in
  `src/sts_combat_rl/comm/protocol.py`.
- stdout is reserved for protocol commands; debugging uses stderr or log files.

Prefer one authoritative implementation over parallel convenience flows. Add
an abstraction only when it removes real duplication or enforces a needed
boundary.

## Branch Collaboration

The current integration line is `codex/integration-current`.

- Create focused task branches named `codex/<topic>` from the integration line.
- Give each task branch a clear file or subsystem ownership boundary.
- The task model commits its work and reports tests, known gaps, and migration
  or documentation impact.
- The integration owner reviews the change, runs the required gates, and then
  merges it into `codex/integration-current`.
- Do not use a dirty `main` worktree as the base for parallel development.
- Do not revert or overwrite unrelated changes from other agents or branches.

Phase gates verify the actual generating controller and provenance, not only
the shape of an output artifact.
