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

The actual Slay the Spire game is the final authority for game mechanics and
live runtime behavior. The pinned external `sts_lightspeed` integration is the
current authoritative simulator implementation for this repository's
large-scale training, native search, restored-battle evaluation, and simulator
gates. If the simulator and the real game disagree, the disagreement is a
simulator fidelity issue to document, test, and resolve; repository Python code
must not patch around it by inventing local game mechanics.

Within that simulator boundary, this repository may:

- select legal actions;
- search copied simulator states;
- encode player-visible observations;
- collect and migrate datasets;
- train models;
- evaluate controllers.

It must not reimplement Slay the Spire mechanics. Simulator state mutation,
legal-action enumeration, battle-start restore, encounter selection, and hidden
future sampling must come from `sts_lightspeed` or a future explicitly adopted
simulator integration, then remain subject to real-game compatibility checks
before any live-game claim.

Real `sts_lightspeed` gates run through WSL. Game files, simulator binaries,
save files, and large artifacts do not belong in this repository.

Large or long-running WSL simulator workloads are expected to be explicitly
sharded and run with parallel workers. A single-worker run is a small
smoke/debug path, not the default execution mode for source-generation, restore
verification, coverage gates, reachability reports, teacher collection,
restored evaluation, fixed-cohort comparison, or training-scale evidence. The
parallelism requirement applies to each expensive stage separately; running
source generation in parallel does not make a later coverage, restore,
teacher, evaluation, or comparison gate acceptable as an undocumented
single-worker run. A `smoke` label does not override the actual expected or
observed cost of a stage. Scale and long-running diagnostic runs should choose
their worker target from the host logical CPU count by default, capped by shard
count and documented memory or simulator limits. The current maintainer
workstation has 16 logical cores, so 16 workers is the default target unless
the report documents a lower-worker resource or tooling constraint. Reports for
such workloads must preserve enough runtime provenance to reproduce every
stage of the execution plan, including shard identity, worker count,
seed/source-run or cohort-record ranges, wall-clock cost, and any explicit
reason a stage used one worker.

## Real Game Runtime Boundary

Training and evaluation may run entirely in `sts_lightspeed`, but a controller
claimed to be live-game runnable must also operate behind the same public
decision and legal-action contract in the actual game through CommunicationMod.

The live runtime adapter owns:

- parsing player-visible CommunicationMod snapshots into the sanitized public
  decision context;
- constructing the legal action list with stable public identities, duplicate
  occurrence disambiguation, target parameters, and command payloads;
- invoking an `OnlineController` without simulator-only fields;
- mapping the selected legal action back to a CommunicationMod protocol
  command;
- recording runtime provenance, source format, missing fields, unsupported
  fields, and selected action identity.

The live adapter must not create a second feature contract, infer hidden state,
call local Slay the Spire mechanics to invent legal actions, or let debug output
contaminate stdout protocol commands. If a live state cannot be mapped to the
published decision contract, the adapter fails closed with an explicit
unsupported-state record or named fallback instead of emitting an arbitrary
action.

Captured CommunicationMod combat snapshots are the required compatibility test
surface. Interactive live-game smoke tests are useful, but they do not replace
fixture-based regression coverage.

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

The latest `main` does not yet carry this complete public context. That
limitation belongs in `current_status.md`; it does not narrow the architectural
target.

The current immediate-combat contract is `public-tactical-v2`. Its structured
state and action objects are authoritative; fixed-size numeric vectors are a
compatibility view derived from those objects. The contract preserves explicit
missing values and field-parity classifications so a simulator-only detail
cannot silently become a live-runtime input. T013 must consume this contract
rather than creating another live feature representation.

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

Live CommunicationMod control is another distinct boundary: the external game
advances state and the repository only consumes snapshots and emits protocol
commands. It still uses the shared controller and action-selection contract.

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

`main` is the only integration line. The authoritative workflow is
[`collaboration_workflow.md`](collaboration_workflow.md).

- One published task corresponds to one fresh branch and one pull request.
- Every task branch starts from latest `main`.
- Parallel tasks use isolated worktrees and never switch branches in a shared
  worktree.
- The main maintainer owns project documentation, task publication, review,
  and merging.
- Task implementers own only their task branch and report documentation impact
  rather than rewriting authoritative project documents.
- Unmerged branches and artifacts are not implemented project capabilities.
- Do not revert or overwrite unrelated changes from other tasks.

Phase gates verify the actual generating controller and provenance, not only
the shape of an output artifact.

Task dependencies are contracts, not local filesystem accidents. A later task
may depend on a predecessor's merged schema, command surface, fixture, or
documented artifact-generation procedure. It must not depend on an uncommitted
worktree file, a one-off smoke output, or a temporary checkpoint that only
happened to exist on one machine.

GB-scale pools, teacher datasets, checkpoints, and coverage shards remain
outside Git. When raw files are intentionally kept for follow-up work, they must
live under a stable ignored/local retention path rather than a disposable review
worktree, and the durable contract must be a lightweight manifest or report
with schema, provenance, hashes, sizes, regeneration commands, compatibility
requirements, retention owner/reason, and deletion conditions.

GB-scale finalization paths must avoid loading all shard records into memory
when a streaming or summary-preserving contract can express the same result.
For JSONL source pools, prefer metadata-first validation plus streaming record
copy/remap into the merged artifact. For coverage, restore, reachability, and
comparison reports, prefer aggregation from shard-level summaries and artifact
identities instead of reopening multi-GB source pools. Full record loads are
reserved for small fixtures, smoke/debug work, or a documented schema need that
cannot be satisfied by streaming validation.
