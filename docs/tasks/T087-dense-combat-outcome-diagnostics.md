# T087: Dense Combat Outcome Diagnostics And Blind Trace Audit Surface

## Objective

Make Battle-policy quality observable before introducing another Combat search algorithm or another learned Battle component.

T087 does **not** attempt to improve the Battle controller. It freezes the current accepted unguided Search-v2 baseline and adds a reproducible dense terminal diagnostic surface that distinguishes materially different losses and wins which are currently collapsed into the same binary outcome.

The task also produces a small blind-review trace bundle and rubric so a knowledgeable STS player can audit whether failures appear tactically poor, strategically doomed before combat, or ambiguous. Human review is auxiliary diagnostic evidence only; it is never a training target or promotion gate.

The immediate successor, if T087 succeeds, is a separately published Combat baseline tournament comparing the accepted Search-v2 baseline with simple Beam/best-first and stronger classical MCTS designs under this fixed diagnostic surface.

## Publication Baseline

Planner publication base:

`main @ b38c0584e4aac9172f9da4426004bfb64a13a41d`

Accepted active simulator identity:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d62ff35579b54d70a7428afdf84743c94df3fe0c`

T085 is complete with `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`. T086/PR #99 is deferred before specification approval so its expensive Non-Combat targets are not generated under a Battle baseline that may immediately be replaced.

## Research-Ledger Link

T087 implements the first step of the post-T085 research sequence recorded in research-ledger issue #85 on 2026-09-09:

1. dense Combat diagnostics;
2. classical Combat baseline tournament;
3. freeze the strongest credible non-learned Battle baseline;
4. only then resume the minimal self-generated Non-Combat learner;
5. true mutual Battle/Non-Combat co-evolution remains downstream of independent improvement evidence on both sides.

## Dependencies

Required accepted dependencies:

- T005: fixed structural Battle evaluation substrate.
- T012/T018: structured Battle outcome and terminal visible-resource identity surfaces.
- T016: public-context/replay audit semantics.
- T052: retained hard Boss/later-act Battle cohort.
- T078: restored public-context/legal-action fidelity.
- T081: scientific artifact eligibility gate.
- T085: accepted current-native identity, frozen unguided Search-v2 baseline, and exact A/B/C evaluation selections.

No new native capability is a dependency. If the required public entry/terminal Combat fields cannot be obtained from the accepted current simulator and existing STSRL trace/snapshot surfaces, T087 must fail closed rather than silently add a simulator semantic change.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: exact T085 A/B/C selected Battle records and restore evidence; exact current native identity; exact frozen baseline controller; all T087 raw entry/terminal snapshots, action traces, dense diagnostic rows, rescue-ladder rows, blind-audit bundle, report, and retention identities.

Reuse mode: `scientific_quality_claim` for the diagnostic validity claim only. T087 does not make a Battle-policy improvement claim.

Claim boundary: T087 may establish only that the frozen Combat evaluation can reproducibly expose a denser, auditable description of Battle outcomes and a bounded HP-rescue intervention diagnostic. It does not establish that any new controller is stronger, that the dense metric is a correct training reward, that HP rescue is a natural-game utility, or that human judgments are ground truth.

Required predicates: exact selected-record identity; exact restore/public/legal parity; exact native identity; exact frozen Battle controller; complete raw entry and terminal fields; diagnostic fields recomputable from retained raw evidence; no outcome-conditioned record replacement; exact rescue intervention identity; blind trace bundle separable from hidden provenance mapping.

Unavailable-fact behavior: any required identity, raw field, restore fact, terminal outcome, metric denominator, trace occurrence, artifact hash, or provenance field that is missing, conflicting, malformed, filename-inferred, or unavailable fails closed to `INCOMPLETE`.

## Frozen Battle Controller

Every formal natural Battle execution in T087 uses exactly:

- native `BattleScumSearcher2` / Search v2;
- nominal simulations: `100`;
- root selection: `highest_mean`;
- policy-prior callback: none;
- learned leaf-value callback: none;
- native rollout: `playoutRandom`;
- native terminal evaluation: `evaluateEndState`;
- action space: `ActionSpaceConfig.initial_no_potions()`;
- native identity `d62ff35579b54d70a7428afdf84743c94df3fe0c`.

Reuse the exact T085 baseline@100 record-level Search randomness/seed plan. T087 must not invent a new controller seed mapping after seeing dense outcomes.

Search@400, Search@1600, Beam, MCTS variants, learned guidance, root priors, heuristic priors, and policy/value models are out of scope for this task.

## Formal Fixed Cohort

Use the exact T085 accepted A/B/C selections, with no recollection or reselection:

- Cohort A: exact T052 hard/stress 93-record cohort, SHA-256 `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`;
- Cohort B: exact T085 selected 192 records, 96 Act 1 and 96 Act 2+;
- Cohort C: exact T085 current-policy occupancy selection, 128 records.

Accepted T085 selection manifest SHA-256:

`d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752`

Accepted T085 restore-evidence SHA-256:

`0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef`

The combined natural diagnostic cohort is therefore exactly 413 selected Battle records.

Before formal execution, every record must pass the existing T085/T078 restore, public-context, ordered-legal-action, source identity, and native-identity checks. No failed record may be dropped or replaced.

## Raw Evidence Contract

For each of the 413 natural Battle runs retain enough raw evidence to recompute every dense diagnostic without trusting a precomputed scalar.

### Entry fields

At minimum retain:

- cohort and exact record identity;
- Act/floor/room/encounter identity available from accepted public/native metadata;
- player current HP at Battle start;
- player max HP at Battle start;
- ordered enemy identities;
- each enemy's Battle-start current HP;
- Battle-start total enemy HP = sum of non-negative current HP values;
- Battle-start alive-enemy count;
- visible potion identities/count and other already-supported visible terminal-resource provenance needed for audit;
- exact controller/native/action-space provenance.

Battle-start total enemy HP must be positive and finite.

### Terminal fields

At minimum retain:

- authoritative terminal Battle outcome;
- terminal player current HP;
- ordered surviving/enumerable enemy identities exposed at the terminal snapshot;
- each terminal enemy current HP when present;
- terminal total enemy HP = sum of non-negative current HP values;
- terminal alive-enemy count;
- total controlled Battle action count;
- turn count if the existing accepted trace/state surface exposes it without semantic invention;
- battle potion-use/discard action count derived from the retained action trace when identifiable from accepted action kinds;
- terminal visible resources already available through the structured outcome surface;
- native simulator/search cost and wall-clock diagnostics where already emitted by the canonical evaluator.

A field that is explicitly optional above may be reported unavailable; required metric fields may not.

## Dense Diagnostic Vector v1

For each natural Battle run compute and retain the following versioned diagnostics from raw entry/terminal evidence.

### Common counts

```text
enemy_count_initial
enemy_count_alive_terminal
enemy_count_killed = enemy_count_initial - enemy_count_alive_terminal
enemy_kill_fraction = enemy_count_killed / enemy_count_initial
```

Require `enemy_count_initial > 0`; `enemy_kill_fraction` must be finite in `[0,1]`.

### Loss-side distance

For authoritative player-loss outcomes:

```text
enemy_hp_remaining_fraction =
    terminal_total_enemy_hp / battle_start_total_enemy_hp

enemy_damage_fraction = 1 - enemy_hp_remaining_fraction
```

Both must be finite. The retained raw values, not clipping, must justify the expected `[0,1]` range. Material violations are `INCOMPLETE` and should be localized rather than silently clamped.

### Win-side retention

For authoritative player-victory outcomes:

```text
player_hp_remaining_fraction_of_max =
    terminal_player_hp / battle_start_player_max_hp

net_player_hp_delta =
    terminal_player_hp - battle_start_player_hp
```

`player_hp_remaining_fraction_of_max` must be finite. T087 does not call `-net_player_hp_delta` gross damage taken because in-Battle healing can make net HP change differ from gross damage.

### Signed terminal margin

Define exactly one diagnostic scalar:

```text
combat_terminal_margin_v1 =
    + player_hp_remaining_fraction_of_max     on PLAYER_VICTORY
    - enemy_hp_remaining_fraction             on PLAYER_LOSS
```

Interpretation is intentionally local and transparent:

- positive values are wins, with larger positive values retaining more max-HP fraction;
- values near zero on the negative side are losses where little enemy HP remained;
- large negative magnitude indicates much enemy HP remained.

This scalar is a **diagnostic**, not a learned reward, Search heuristic, promotion score, or replacement for win/loss. T087 must retain the decomposed components so later tasks never need to rely on this scalar alone.

## Consistency Gates

For every natural diagnostic row:

1. outcome must be authoritative `PLAYER_VICTORY` or `PLAYER_LOSS`;
2. all required denominators must be positive;
3. all required numeric fields must be finite;
4. `enemy_count_killed + enemy_count_alive_terminal == enemy_count_initial` when the accepted terminal representation preserves all enemy occurrences needed for that identity; otherwise the row is incomplete rather than guessed;
5. victory rows must have non-negative `combat_terminal_margin_v1`;
6. loss rows must have non-positive `combat_terminal_margin_v1`;
7. diagnostic values must recompute byte/number-equivalently from the retained raw row under the versioned formula;
8. the diagnostic layer must not alter controller decisions, Battle transitions, Search, RNG, or simulator state.

## Bounded HP-Rescue Diagnostic

T087 includes one small intervention diagnostic motivated by the question: "How much additional entry HP would this exact controller need before the same Battle becomes winnable?"

This is **not** a natural-policy outcome metric.

### Selection

After the natural 413-record evaluation is complete, consider only natural baseline losses.

Select exactly 24 loss records:

- 8 from Cohort A;
- 8 from Cohort B;
- 8 from Cohort C.

Within each cohort, rank loss-record identities by:

`sha256(b"T087-hp-rescue-v1\n" + canonical_record_identity_bytes)`

and take the first 8. No dense metric, encounter difficulty, deck quality, or human judgment may affect this selection.

If any cohort has fewer than 8 valid natural losses, T087 is `INCOMPLETE`; do not borrow quota from another cohort.

### Intervention ladder

For each selected loss, preserve the same deck, relics, potions, encounter, native identity, action space, controller, and exact T085 baseline record-level Search randomness plan.

Change only Battle-start current HP using the existing accepted same-ascension Battle-start HP-addition transform. Let:

```text
hp_gap_to_max = max(0, player_max_hp - player_start_hp)
```

Evaluate every unique sorted value in:

```text
{0,
 min(5, hp_gap_to_max),
 min(10, hp_gap_to_max),
 min(20, hp_gap_to_max),
 hp_gap_to_max}
```

No potion or encounter transform is allowed.

Retain every ladder outcome. Report:

- `min_observed_extra_hp_with_win` if any tested positive-HP intervention wins;
- `censored_no_win_at_max_hp=true` if the max-HP intervention still loses;
- the complete tested `(extra_hp, outcome, terminal_margin)` sequence.

Do **not** assume monotonicity, interpolate between tested HP values, binary-search a threshold, or call this an exact minimum HP-to-win. Low-HP mechanics and Search stochastic structure can make the intervention non-monotone. The ladder is only a bounded rescue/robustness diagnostic.

If the existing accepted HP-addition transform cannot reproduce the exact record apart from HP, stop as `INCOMPLETE`; do not add a local simulator workaround.

## Blind Human-Audit Bundle

T087 must produce a blind-review-ready bundle; completing human labels is **not** required for T087 acceptance.

### Trace selection

Select exactly 24 natural runs after dense diagnostics are complete:

- 8 wins, SHA-ranked within all wins;
- 8 near-boundary losses with `enemy_hp_remaining_fraction <= 0.25`, SHA-ranked;
- 8 deep losses with `enemy_hp_remaining_fraction >= 0.75`, SHA-ranked.

Use domain-separated key:

`sha256(b"T087-human-audit-v1\n" + canonical_run_identity_bytes)`.

If a requested stratum has fewer than 8 records, fill only from the nearest adjacent outcome/margin stratum under a deterministic threshold-relaxation rule documented before viewing trace contents. Do not hand-pick interesting battles.

### Blind bundle content

Each trace must contain player-visible Battle-start context and an ordered action/state log sufficient for an STS player to understand the fight. The user-facing trace must not expose:

- controller/algorithm name;
- Search budget;
- dense diagnostic scalar;
- internal Search telemetry;
- hidden simulator state;
- artifact filenames that reveal cohort/controller identity.

A separate hidden provenance map must retain exact source/controller/artifact identities.

### Review rubric

Provide a structured form with exactly these primary fields:

1. `start_winnability`: `clearly_winnable | difficult_but_winnable | likely_doomed | uncertain`;
2. `combat_execution_quality`: `major_tactical_error | minor_tactical_error | no_obvious_major_error | uncertain`;
3. `dominant_failure_source`: `combat_execution | precombat_state | mixed | uncertain`;
4. `earliest_decisive_step_or_turn`: optional free text/identifier;
5. `confidence`: integer 1..5;
6. `notes`: optional free text.

Human labels produced later are auxiliary failure-analysis evidence only. They are forbidden as policy targets, value targets, card/deck rankings, Search heuristics, or sole controller-promotion evidence.

## Formal Report

Report at minimum:

- exact native/controller/cohort/artifact identities;
- 413/413 restore and execution completeness;
- win/loss counts by A/B/C;
- distribution summaries for `combat_terminal_margin_v1` and its decomposed components by cohort/outcome;
- loss `enemy_hp_remaining_fraction` quantiles;
- win `player_hp_remaining_fraction_of_max` quantiles;
- enemy-kill fraction distribution;
- action/turn/resource-cost diagnostics where available;
- 24-record HP-rescue ladder outcomes and censoring count;
- 24-record blind human-audit bundle identity and hidden-map identity;
- confirmation that no human label entered any algorithm or terminal classification.

No statistical significance claim between controllers is allowed because T087 evaluates only one frozen controller.

## Terminal Classification

Emit exactly one terminal classification.

### `DENSE_COMBAT_DIAGNOSTICS_READY`

Require all of:

1. exact artifact eligibility and native identity pass;
2. exact A/B/C selection and restore gates pass for 413/413 records;
3. all 413 natural runs complete under the frozen baseline;
4. dense diagnostic raw fields and recomputation gates pass for every row;
5. the exact 24-record HP-rescue sample and all required ladder variants complete without unauthorized transform changes;
6. the 24-record blind human-audit bundle and hidden provenance map are retained and hash-bound;
7. report and retention manifest are complete.

This classification means the diagnostic surface is ready for later controller comparison. It makes no controller-quality claim.

### `INCOMPLETE`

Any required identity, restore, raw-field, formula, execution, HP-rescue, blind-bundle, artifact, provenance, or retention failure.

There is no success/harm/not-established class because no competing controller is evaluated.

## Required Artifacts

Retain and hash at minimum:

1. input eligibility/identity report;
2. exact 413-record natural-run manifest;
3. raw entry/terminal evidence rows;
4. versioned dense diagnostic table;
5. HP-rescue selection manifest and ladder outcomes;
6. blind human-audit trace bundle;
7. hidden trace provenance map;
8. human-review rubric/schema;
9. final report;
10. retention manifest with hashes, sizes, regeneration commands, compatibility requirements, and deletion conditions.

Formal simulator work must follow the repository detached-job/resource-admission conventions and record effective workers/shards. A smoke/canary may validate plumbing but is not formal evidence.

## Native-Change Boundary

`native_change_required: false` at publication.

T087 is intended to use existing accepted snapshots, traces, restore, public projection, structured outcomes, and HP-addition rebuild support.

If implementation discovers that a **required** dense raw field cannot be obtained without changing `sts_lightspeed`, stop before native modification and return the exact missing-field evidence to Planner. Do not silently widen T087 into native telemetry or semantics work.

## Out Of Scope

- Beam Search, A*, best-first, MCTS redesign, Search@400/1600 comparison;
- any learned Battle policy/value/prior;
- any new learned reward/loss based on the dense diagnostics;
- T086 Non-Combat training or target generation;
- T066 joint/alternating learning;
- simulator semantic changes;
- hidden-state features;
- human labels as training supervision or controller-promotion ground truth;
- manual selection of "interesting" battles.

## Acceptance Criteria

1. Exact 413-record T085 A/B/C selection is restored and evaluated with no replacement.
2. Battle remains exactly unguided Search v2@100/highest_mean under accepted native `d62ff355...`.
3. Every natural run retains recomputable dense raw entry/terminal evidence and versioned diagnostic fields.
4. Win/loss remains authoritative; dense diagnostics supplement rather than redefine outcome.
5. The exact 24-loss HP-rescue sample completes the frozen intervention ladder with no monotonicity assumption.
6. The exact 24-trace blind audit bundle and rubric are retained with a separate hidden provenance map.
7. No human label is required for task completion and no human judgment enters algorithms or promotion criteria.
8. Exactly one terminal classification is emitted from retained evidence.
9. Final result/lifecycle documentation lands on the same PR head after Maintainer and Planner review.

## Successor Boundary

If `DENSE_COMBAT_DIAGNOSTICS_READY`, Planner should publish a separate Combat baseline tournament task. The intended candidate set is:

- accepted unguided Search v2@100;
- Search v2@400 as a higher-budget reference;
- one simple transparent Beam/best-first search;
- one stronger classical MCTS design if its implementation boundary is sufficiently clear.

A* should be included only if a meaningful cost/heuristic contract exists; otherwise a weighted best-first formulation should be named honestly rather than called classical A*.

The tournament must compare win/loss **and** the T087 dense diagnostic vector under matched states and matched simulator-step/wall-clock accounting. A small blinded human paired-trace audit may be used as auxiliary failure-analysis evidence but not as the sole promotion gate.

Only after the strongest credible non-learned Combat baseline is frozen should Planner reopen/materially amend T086 or publish its replacement. T066 remains DRAFT.