# T096: Battle Public-Information Hidden-Future Sampler Pilot

Artifact Eligibility Required: true

## Objective

Establish and validate the first authoritative Battle hidden-future sampling
capability for the normal-information/no-SL research line.

T096 has two inseparable scientific deliverables:

1. freeze a versioned, visibility-aware **current Battle public-information
   state** (I_t); and
2. expose a native-owned sampler that can produce multiple full simulator
   Battle states whose public-information projection is exactly the same
   (I_t), while hidden RNG/future state is allowed to differ.

The governing relation is:

```text
full native Battle state S_t
        |
        | game-mechanics visibility / current player knowledge
        v
public-information state I_t
```

A sampled particle `S'_t` is public-consistent only if:

```text
public_information_projection(S'_t) == I_t
```

T096 is a **sampler-correctness and native-feasibility pilot**.

It does not ask whether 2/4/8/16/32 particles are sufficient for stable action
values. It does not run an Oracle-aggregation learning experiment, train a
student, alter Battle Search, promote a controller, or close the full T034
normal-belief-search direction.

The immediate scientific question is narrower:

> can the simulator generate genuinely different hidden Battle futures while
> preserving exactly what a normal player currently knows?

## Publication Baseline

Publication base:

`main @ 461b9b34def89698098e969c9e19c77f5a50602e`

Accepted native source manifest at publication:

- integration repository:
  `https://github.com/lsmfttb/sts_lightspeed.git`;
- active integration branch:
  `refs/heads/stsrl/main`;
- exact integration commit:
  `20a6c2b3a9cea817c988178b814f083ff889853f`;
- upstream base:
  `7476a81954020087da31d41d16fddf475746ec2d`.

Relevant accepted lineage:

- T014: native public-projection boundary;
- T015/T016: sanitized public context/history and artifact propagation;
- T020: governed native fork integration line;
- T034: original public-consistent hidden-future sampler direction;
- T076/T078: checkpoint branch isolation and restore/public-context fidelity;
- T079: future-dynamics-complete Battle-state identity evidence;
- T092: dense internal Search telemetry surface;
- T094/T095: repeated-public-state diagnostics, ending with
  `EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE`.

T095 established that passive exact-state recurrence is not a viable substitute
for active hidden-future sampling: its `k_min=8` surface was empty, and even
`k_min=4` had zero qualifying repeated public/action-pair aggregates.

T096 therefore does not enlarge T092-style passive collection. It tests the
native capability required to create the missing multi-realization surface
deliberately.

## Research Semantics

### Current information state, not complete decision-history equality

T096 supersedes the older conservative interpretation that two particles must
have identical complete stored public decision histories.

The scientific state for no-SL Battle reasoning is the **current information
available to the player**.

Past history matters only insofar as it changes what the player can currently
know.

For example:

- after Headbutt places a known card on top of the draw pile, the fact
  `known top card = X` belongs to the current information state;
- the historical fact that Headbutt was played on an earlier step need not be
  retained solely to define particle equivalence once the current knowledge is
  represented;
- Frozen Eye makes draw-pile order public;
- Runic Dome makes enemy intent hidden;
- ordinary Battle states hide draw-pile order and expose current enemy intent.

The durable target is therefore Markov-like with respect to player knowledge:

```text
current visible Battle mechanics
+ persistent public run resources/context relevant now
+ current knowledge/constraints on otherwise-hidden quantities
+ current visibility status of those quantities
```

T096 must not require raw historical trajectory identity when two states have
the same complete current player information.

### Unified visibility framework

Headbutt, Frozen Eye, Runic Dome, and similar mechanics are not scientific
exceptions. They alter the projection from full native state to player
information.

The versioned T096 visibility contract must be able to classify a native fact
or hidden-derived quantity as at least one of:

- **public exact**: the player currently knows the exact value;
- **hidden**: the player currently does not know the value;
- **public constraint / partial knowledge**: the player knows a constraint or
  subset of the hidden structure without knowing the full value;
- **unsupported fidelity**: the current native simulator/projection cannot
  faithfully determine the game's visibility/knowledge semantics.

Names and serialization details remain implementation choices, but these
semantic distinctions are mandatory.

Representative semantics include:

```text
ordinary draw pile:
    order hidden

Headbutt-like known-top state:
    known top card public
    deeper unrevealed order hidden

Frozen Eye:
    draw-pile order public

ordinary enemy:
    current intent public

Runic Dome:
    current intent hidden
```

If the current `sts_lightspeed` fork does not faithfully implement a named
mechanic, T096 must report that as native fidelity unavailable. It may not
silently special-case the mechanic in Python or pretend the visibility fact is
known.

### No PRNG cracking objective

STS/lightSpeed is deterministic under seeded PRNG state. In a purely Bayesian
model, a sufficiently long observation history can contain information about
the hidden PRNG state.

T096 explicitly does **not** define normal play as reverse engineering the
deterministic game seed or PRNG internals from prior random observations.

The selected information regime is ordinary no-SL play:

- use information legitimately exposed by game mechanics;
- preserve facts the player currently knows;
- do not expose or infer hidden PRNG internals merely because deterministic
  reverse engineering might theoretically recover them;
- resample hidden future randomness that remains unknown to the player.

Therefore T096 must not describe its particles as exact samples from the
deterministic-seed Bayesian posterior unless a later task separately proves
that stronger claim.

The accepted v1 claim is a native, public-consistent **future-randomization
proposal distribution** for normal play.

## Native Mechanics Boundary

The real/native simulator remains the mechanics authority.

At the publication baseline, `BattleContext` contains multiple future-relevant
RNG streams including:

- `aiRng`;
- `cardRandomRng`;
- `miscRng`;
- `monsterHpRng`;
- `potionRng`;
- `shuffleRng`.

T079 also established that future-dynamics-complete Battle identity contains
more than RNG counters: ordered card/pile state, Player and Monster state,
queues/current card item, control flags, and all relevant future-dynamics
state.

Current checkpoint capture/restore already copies `GameContext`,
`BattleContext`, and `battleActive`, with branch-isolation repairs accepted
through T076/T078.

These capabilities are a branching substrate only. They are not yet an
authoritative hidden-future sampler.

### Required ownership

Any operation that changes:

- RNG internal state;
- unseen draw-pile order;
- hidden/current enemy move state where the move is not public;
- future random-effect state; or
- another mechanics-owned hidden Battle quantity

must be owned by the native simulator or another explicitly authoritative
native mechanics boundary.

Python may request particles, validate public projections, aggregate evidence,
and write reports. Python must not recreate STS random mechanics by directly
patching hidden state or by maintaining a second hand-written simulator.

The exact native API shape, helper decomposition, C++ class layout, random seed
plumbing, process topology, and serialization are ordinary
Maintainer/Implementer decisions unless they alter the scientific semantics in
this contract.

## Public-Information Projection Contract

T096 must introduce one versioned Battle public-information projection suitable
for particle parity checks.

It may reuse accepted T011/T014/T015 structures where valid, but it must not
inherit their ordinary-state visibility assumptions when a mechanic changes
what is currently visible.

At minimum the projection must preserve all currently public Battle facts needed
to distinguish legal player decisions, including:

- current player HP/max HP, block, energy and public statuses;
- current hand and other public card-pile membership;
- current draw-pile size;
- public persistent deck/relic/potion/resource facts available at the Battle
  decision;
- current monsters and all currently visible monster state;
- current turn/Act/floor/encounter context required by the Battle decision;
- ordered public legal-action identities;
- visibility/knowledge constraints for quantities that may be hidden or
  revealed by mechanics.

The projection must never include hidden RNG internals merely to make parity
checking easier.

The existing `public-tactical-v2` rule "draw order is never read" and its
ordinary visible-intent assumptions are not sufficient by themselves for this
task.

### Public action identity

Native replay-only action bits must not become normal-agent information merely
because the sampler is native.

Public action identity follows the already-established public-action meaning:
visible scope/kind/parameters/label/selected public entities as required to
distinguish the player's legal choices, excluding replay-only/native-private
identity.

The exact serialized identity may reuse the current accepted public action
contract.

## Particle Semantics

For an anchor native Battle state `S_t` at a player decision:

1. derive the frozen public-information state `I_t`;
2. produce one or more native full-state particles `S'_t`;
3. require every particle to project exactly back to `I_t`;
4. preserve every fact constrained by `I_t`;
5. allow only currently hidden quantities to vary;
6. retain enough private audit metadata to prove hidden diversity without
   exposing that metadata to a normal controller/model.

A particle is invalid if its public projection differs from the anchor by even
one material public fact or legal public action.

A sampler run is invalid if nominally different particles differ only by
irrelevant metadata while all future-dynamics hidden state remains identical.

### Independence language

T096 may call two particles **distinct hidden realizations** when their
future-dynamics-complete private native states differ.

T096 must not call particles IID posterior samples, independent game seeds, or
independent Bayesian draws unless separately proved.

Artifact ID, source-record ID, controller-arm ID, and sampler invocation count
are not sufficient evidence of hidden-state independence.

## Pilot Scope

The scientific contract applies to Battle player-decision states generally.

For acceptance evidence, keep the pilot small and local-first.

The required minimum evidence must include:

1. ordinary Battle states where draw order is hidden and enemy intent is
   public;
2. at least one native-supported **draw-knowledge** case in which the player's
   current knowledge constrains hidden draw order more strongly than the
   ordinary state;
3. at least one native-supported **intent-visibility** case comparing ordinary
   visible intent with a mechanics state where intent is hidden, if the pinned
   native simulator faithfully supports that mechanic.

Headbutt and Frozen Eye are preferred representative draw-knowledge cases.
Runic Dome is the preferred intent-visibility case.

If one of these named mechanics is not faithfully implemented by the native
simulator, the report must identify the exact native fidelity gap and use the
terminal rules below. It may not replace the missing mechanic with invented
Python semantics.

Battle-start first-player decisions are expected to be the simplest mandatory
anchor surface. Mid-Battle states may be included and are scientifically
desirable, but T096 must not claim general arbitrary-mid-Battle support unless
the visibility/knowledge projection actually preserves the required current
knowledge there.

The pilot is deliberately small; no large-scale data generation is authorized.

## Distribution-Sanity Contract

Public parity and hidden diversity are necessary but not sufficient.

A sampler that always chooses one arbitrary hidden future can preserve the
public state while badly distorting the game distribution.

T096 must therefore retain at least one bounded reference check where the
future-randomization distribution can be independently assessed.

At minimum:

- include one draw-order reference family in which the currently visible cards
  are fixed and the distribution of one or more still-hidden next-card events
  has an independently computable or native-brute-force reference;
- compare sampler frequencies with that reference using a preregistered,
  reported statistical distance or confidence check;
- include enough samples for the check to detect a grossly biased sampler, but
  keep the run local-first and bounded.

A second non-draw RNG reference is encouraged where the native mechanics make a
clean independent comparison possible, but it is not a mandatory scientific
gate for T096.

The reference check validates only the bounded tested marginal. It does not
prove that the full particle distribution is the exact deterministic-seed
posterior.

## Artifact Eligibility Contract

### Inputs

Eligible inputs include:

- current natural or fixed Battle checkpoints/artifacts whose lineage validates
  under existing repository contracts;
- fresh bounded simulator states generated solely for this T096 pilot;
- exact current public/native contracts on the publication baseline;
- a reviewed temporary native fork branch derived from the pinned
  `stsrl/main` integration line, if native changes are required.

A native fork change is expected to follow the T020 maintenance policy:
temporary task branch, exact source identity, reviewed STSRL integration, and
no unrecorded local native state.

### Reuse mode

`scientific_quality_claim`.

### Required predicates

Before a successful T096 terminal, all of the following must hold:

- STSRL publication lineage and exact native source identity validate;
- the new public-information projection is versioned and rejects hidden RNG
  leakage;
- every accepted particle has exact anchor-vs-particle public-information
  parity;
- ordered public legal-action parity holds for every accepted particle;
- hidden diversity is demonstrated in future-dynamics-relevant native state;
- sampler output is reproducible under an explicit sampler seed/configuration;
- no controller/model input contains private particle RNG state, hidden draw
  order when that order is not public, or other hidden particle-only facts;
- visibility-changing mechanics are represented through the common visibility
  framework rather than ad-hoc scientific exceptions;
- native fidelity gaps are explicit and fail closed;
- the mandatory bounded distribution-sanity reference passes;
- the task remains a sampler pilot only: no model training, Search-value
  aggregation gate, policy promotion, complete-run conclusion, or T066 work.

### Unavailable-fact behavior

Missing, malformed, conflicting, inferred, filename-derived, substitute,
unverifiable, or unsupported material facts fail closed.

Python reconstruction of hidden Battle mechanics is ineligible evidence.

## Required Evidence

The retained T096 report must state at least:

- exact STSRL implementation/evidence head;
- exact native fork repository/ref/commit used;
- public-information projection schema/version;
- sampler schema/version and sampler seed/configuration;
- anchor count and anchor provenance;
- particle count per anchor and total particle count;
- public-parity pass/fail counts;
- legal-action parity pass/fail counts;
- private hidden-state diversity summary without exposing hidden state to the
  normal controller path;
- which visibility/knowledge mechanic families were exercised;
- exact native fidelity gaps/unsupported cases;
- distribution-sanity reference definition, sample count, statistic and result;
- peak resource/runtime evidence sufficient to show the pilot remained bounded;
- terminal classification.

A private audit representation may hash or compare hidden native state for
diversity validation. It must not become a public policy/model feature.

## Terminal Classifications

### `PUBLIC_HIDDEN_FUTURE_SAMPLER_PILOT_READY`

Use only if:

- the visibility-aware public-information projection is valid;
- all accepted particles preserve exact public and legal-action parity;
- meaningful hidden future diversity is demonstrated;
- the mandatory distribution-sanity reference passes;
- the ordinary hidden-draw / visible-intent case passes; and
- the pilot demonstrates at least one mechanics-aware visibility/knowledge
  constraint beyond the ordinary case.

This terminal means a separate particle-count convergence task may be
published.

It does not close general T034, prove an exact posterior, prove mid-Battle
coverage, or authorize model training.

### `NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`

Use if the sampler core can be meaningfully exercised, but the current native
simulator cannot faithfully expose enough current visibility/knowledge
semantics to support the required pilot boundary.

This terminal selects native visibility/fidelity repair before particle
convergence.

It is not evidence that hidden-future sampling is scientifically invalid.

### `PUBLIC_HIDDEN_FUTURE_SAMPLER_PARITY_INVALID`

Use if a proposed sampler changes a fact that the public-information projection
requires to remain fixed, changes the public legal-action set/identity, leaks
private state, or cannot prove meaningful hidden future diversity.

Do not proceed to particle convergence.

### `PUBLIC_HIDDEN_FUTURE_SAMPLER_DISTRIBUTION_INVALID`

Use if public parity/diversity are valid but the mandatory bounded
distribution-sanity reference detects a material distortion under its
preregistered check.

Do not proceed to particle convergence until the sampling distribution is
repaired.

### `INCOMPLETE`

Use when required evidence cannot be validly produced or material facts are
missing/invalid.

## Explicit Non-Claims

T096 does not establish:

- exact `P(hidden native state | full deterministic-seed history)`;
- information-set-optimal Q-values;
- the number of particles required for stable decisions;
- Battle policy learnability;
- Battle controller improvement;
- student Search improvement;
- complete-run improvement;
- Battle-to-run continuation value;
- learned Non-Combat improvement;
- deployment readiness;
- complete arbitrary-mid-Battle observability support;
- T034 completion; or
- T066 authorization.

## Out Of Scope

Do not perform or authorize in T096:

- large passive T092-style recollection to chase state collisions;
- Search-v2 teacher target generation across particles;
- 2/4/8/16/32 action-ranking convergence experiments;
- policy/value model training;
- checkpoint selection or student distillation;
- Battle controller promotion;
- complete A20 run evaluation;
- Non-Combat policy work;
- continuation-value training;
- live-game deployment;
- PRNG seed cracking/inference;
- T066.

## Successor Meaning

A successful `PUBLIC_HIDDEN_FUTURE_SAMPLER_PILOT_READY` terminal justifies one
separately published convergence task.

That successor should hold a bounded public-state cohort fixed and measure how
action-value/ranking estimates change as nested particle budgets increase, for
example:

```text
2 -> 4 -> 8 -> 16 -> 32
```

The successor, not T096, owns the compute-feasibility / particle-count go-no-go
decision.

If convergence is poor even at tens of particles, Planner should treat that as
an early architecture/economics warning rather than automatically scaling to
hundreds or thousands of particles.

## Execution Freedom And Material Changes

Maintainer/Implementer own ordinary implementation details including:

- exact native API names;
- C++ helper decomposition;
- Python adapter/helper structure;
- temporary-file/report layout;
- native task-branch naming consistent with T020;
- test organization;
- process topology;
- bounded pilot scheduling;
- CLI shape;
- caching and resource orchestration.

A material change requires Planner amendment and renewed Maintainer exact-head
approval if it changes any of:

- the current-information-state rather than full-history scientific definition;
- the unified visibility/knowledge semantics;
- the no-PRNG-cracking information regime;
- which facts may be resampled versus must remain fixed;
- native mechanics ownership;
- public/legal-action parity requirements;
- hidden-diversity meaning;
- mandatory distribution-sanity requirement;
- terminal classifications;
- successor meaning.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, the Maintainer must independently review the exact task
PR head and post:

```text
SPEC APPROVED

task: T096
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not
require repeated Planner approval unless a material scientific/architecture
change above occurs.

Final landing requires Maintainer final implementation/operational acceptance
and Planner final scientific/architecture acceptance on the same exact final PR
head.

T066 remains unauthorized.
