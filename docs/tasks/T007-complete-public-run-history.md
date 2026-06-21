# T007: Complete Public Run History

Status: `READY`.

## Objective

Establish one typed, versioned, sanitized public run-context contract for
continuation-aware battle decisions. It must retain all facts visible to the
player that can affect later choices, while making every unavailable field
explicit and excluding hidden simulator state.

## Current Main Baseline

`public-tactical-v2` exposes immediate battle state and persistent tactical
resources. T004 pool records retain `public_context_status="unavailable"` and
do not preserve a complete run history, visible map, or visible Act Boss.
`execute_controlled_run` is the authoritative complete-run advancement path,
and T003 provides artifact migrations and decision provenance.

## Dependencies

- T002, T003, T004, and T011 are complete.

## Scope

- Define one nested, versioned public run-context schema that is separate from
  `public-tactical-v2` but can be attached to `DecisionContext`, checkpoint
  records, decision records, trainer-input records, and model-input packing.
- Record an ordered typed history entry for every successfully executed
  player-visible decision in `execute_controlled_run`. Entries must preserve
  the visible pre-decision screen, occurrence-disambiguated public action
  identity and parameters, visible post-decision result/location, and public
  resource changes or explicit missing fields.
- Preserve the complete currently visible map graph, current node, all
  immediately available route choices, visible current-Act Boss, current
  location, and public persistent resource snapshot. Preserve all player-visible
  room/event/reward/shop/rest/treasure/card/relic/potion/key choices and their
  visible results through the typed history; do not reduce history to encounter
  ids or prose.
- Add only the focused `sts_lightspeed` projection/patch surfaces needed to
  expose those native player-visible fields. The simulator remains authoritative
  for screen state and legal actions; repository code may sanitize and version
  projections but must not reconstruct game mechanics or invent unavailable
  facts.
- Build context before a normal-information controller or encoder receives it.
  Preserve missingness and provenance through battle-start capture, portable
  manifest replay, decision persistence, trainer-input migration, and
  model-input packing.
- Add recursive forbidden-field audits. At minimum reject hidden RNG, raw
  native objects/checkpoints, unrevealed future encounters, hidden draw order,
  simulator-only monster internals, and the hidden Act-3 second Boss.
- Migrate legacy artifacts sequentially to the current schema. Historical
  records without reconstructible history/context must retain an explicit
  unavailable or loss declaration; writers emit only the current schema.
- Provide a focused command workflow and a WSL audit that reports seen screen
  types, history length, map/context completeness, missing native fields, and
  forbidden-field failures. CLI code remains parsing and routing only.

## Out Of Scope

- A learned history encoder, continuation-value training, belief search, or
  strategy-quality filters.
- Treating a raw simulator snapshot, native checkpoint, or a captured full game
  state as normal-controller input.
- Fabricating historical events, route edges, screen content, future encounters,
  or the Act-3 second Boss when a native projection is missing.
- Structured terminal battle-resource labels beyond the public history delta;
  T012 owns the dedicated battle-outcome schema.

## Design Constraints

- The long-term context is exactly: public tactical battle state, persistent
  public run resources, typed visible history, complete visible map/routes, and
  visible current-Act Boss. The visible Boss must be recorded as the Boss known
  when the relevant decision was made.
- The schema must carry field-level missingness. An empty list, `null`, and
  unavailable data must remain distinguishable where the simulator can make
  that distinction.
- History ordering is contiguous and append-only within a run. Replaying a
  portable source trace must reproduce the public history available at the
  recorded battle start or fail explicitly; it may not fall back to a partial
  encounter list.
- Allowlisting and validation are recursive. Nested map nodes, rewards,
  actions, resource records, and screen payloads cannot bypass the public
  boundary through generic dictionaries.
- Preserve player-visible properties such as burning-elite marking and legal
  map connectivity when present. Do not silently drop a declared public field
  merely because an older projection omitted it.
- `DecisionContext` may receive a sanitized context object, never an unrestricted
  raw context. Oracle-like controllers may retain their separate simulator
  boundary and information regime, but their datasets/reports must not make
  that state appear in normal-public input.
- Schema/version changes must use the repository artifact-migration framework;
  do not leave permanent legacy branches in business logic.

## Deliverables

- Public run-context/history schema, sanitizer, recursive validator, and
  explicit-missing representation.
- Focused native projection patches plus adapter exposure for complete visible
  map/routes, screens, visible Boss, public resources, and typed results.
- Controlled-run collector integration, checkpoint/manifest persistence,
  decision/trainer/model-input carriage, and sequential migrations.
- Focused command workflow, capture fixtures, forbidden-field tests, and WSL
  public-context audit.

## Acceptance Criteria

- A controlled run appends exactly one contiguous history entry for every
  successful visible decision, including non-combat decisions, and never for a
  failed or unexecuted selection.
- A battle-start record restored through its portable source trace has the same
  sanitized context fingerprint, map graph, visible Boss, and history entries
  as the captured record, or restoration reports a named mismatch.
- The context carries complete visible map connectivity, current node, and
  currently selectable next nodes whenever the simulator supplies them.
- Every declared public field is either present in the sanitized schema or
  listed as explicitly missing. No validator may silently accept an unknown
  nested key.
- Fixtures demonstrate that hidden RNG, draw order, unrevealed encounters,
  simulator internals, raw checkpoints, and hidden Act-3 Boss data are rejected
  or absent from normal-public artifacts.
- Legacy records migrate with explicit context loss; current writers never emit
  `public_context_status="unavailable"` as a substitute for a context object.
- Trainer/model-input round trips retain the context/version/missingness without
  re-reading unrestricted raw snapshots.
- The WSL audit reports coverage honestly. Unseen or unsupported screen types
  remain named gaps and block any claim that the resulting corpus has complete
  context.

## Required Verification

Run the standard local gates, focused context/history/migration tests, a
portable pool restore/context-fingerprint test, and a captured fixture audit
covering at least map, event, rewards, shop, rest, treasure, card selection,
relic selection, and potion-related screens. Run this WSL gate after applying
the task patch stack:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-public-run-context-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

The command must fail nonzero on forbidden-field leakage, invalid history
ordering, or a replay/context mismatch. The PR report must state the exact
screen types observed, fields sourced natively, fields still unavailable, pool
and artifact migration behavior, and why the sampled audit does or does not
support a complete-context claim.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_public_run_context.patch
patches/sts_lightspeed_public_visible_screen.patch
src/sts_combat_rl/sim/public_run_context.py
src/sts_combat_rl/sim/public_run_history.py
tests/test_public_run_context.py
tests/test_public_run_history.py
```

The legacy implementation is not an acceptance reference. Known defects include
inconsistent visible-screen naming, incomplete recursive allowlists, dropped
visible map attributes, and incomplete battle-screen semantics. Selectively
port only behavior that satisfies this specification and current artifact
contracts.

## PR Report

Include task ID, schema versions, native patch coverage, visible screen/context
inventory, migration losses, exact local/WSL verification results, forbidden
field audit evidence, legacy files consulted, known gaps, and any unmet
acceptance criterion.
