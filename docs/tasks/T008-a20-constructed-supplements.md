# T008: A20 Constructed Battle Supplements

Status: `BLOCKED` by T007.

## Objective

Create conservative, seeded, explicitly tagged A20 constructed battle starts
that supplement, but never replace, natural A20 data or natural evaluation.

## Current Main Baseline

T004 can restore natural battle-start records but has no constructed-state
schema or authoritative transform surface. Current records explicitly lack
complete public run context. T007 will make that context available so a
transform can preserve visible history, map, routes, and visible Boss rather
than constructing an ambiguous continuation state.

## Dependencies

- T003 and T004 are complete.
- T007 must merge before implementation starts.

## Scope

- Define a versioned constructed-start artifact that references an immutable
  natural source record and carries source distribution, source checkpoint,
  complete public context, transform-policy version/seed, eligibility result,
  proposal result, requested change, actual authoritative change, and resulting
  distribution kind.
- Add a seeded proposal policy that makes each transform type probabilistic,
  never automatic. Replaying with the same source/configuration/seed must make
  the same proposal and report the same actual transform.
- Support small current-HP additions only after documented observable prior
  opportunities. The cap must combine missing HP, a small configurable policy
  cap, and a conservative bound derived from visible prior opportunity/history;
  it must not trigger on the first battle or create HP above max HP.
- Support simulator-native potion additions only when a visible empty slot and
  documented prior opportunity bound permit them. Additions cannot appear in
  the first battle, exceed capacity, replace a held potion, or use a locally
  invented potion distribution.
- Support native legal same-ascension ordinary/elite encounter alternatives
  chosen from simulator-provided candidates that honor visible history and game
  constraints. Do not locally enumerate encounter rules. Preserve the visible
  Act Boss and never replace it in ordinary training.
- Keep natural, constructed, paired-counterfactual, normal-information, and
  Oracle-like data/output tags separate. Provide a training-mixture manifest
  that reports source counts and never relabels constructed rows as natural.

## Out Of Scope

- A0-to-A20 reconstruction, deterministic hand-authored deck/relic quality
  filters, full-run simulation to certify each small HP change, or a permanent
  natural/constructed mixture ratio.
- Boss replacement in ordinary training. A visible-Boss alternative may only be
  implemented later as a separately tagged paired counterfactual.
- Potion use during battle or a learned continuation-value model.

## Design Constraints

- Every transform retains the original source checkpoint and unmodified source
  context. A transform may alter only its declared authoritative battle-start
  fields; it must never invent history to rationalize the change.
- A proposal that cannot be applied is retained as an audit result but remains
  natural, not constructed. Only an actual state change receives a constructed
  data tag.
- Same-ascension is mandatory. Current A20 states are the only sources and
  outputs of this task.
- Use practical bounded approximations for small HP changes. A replay audit is
  useful for high-impact transforms but is not a per-sample certificate
  requirement.
- The simulator, not repository rules, owns potion identity sampling, encounter
  legality, restore, and state mutation. Missing native support is a named
  unsupported transform, not an invitation to approximate mechanics locally.

## Deliverables

- Constructed-start schema, reader/writer/validator, migrations, and provenance
  report.
- Focused simulator patch/adapter transforms for the supported authoritative
  mutations and legal encounter alternatives.
- Seeded proposal policy, mixed-distribution manifest, transform audit, and
  focused command workflow.
- Tests for first-battle exclusion, opportunity/slot/HP caps, proposal
  stochasticity, repeatability, no-op tagging, Boss preservation, source
  preservation, and information/distribution separation.

## Acceptance Criteria

- The same source/configuration/seed produces identical proposal and actual
  transform records; changing the seed leaves legal low-probability branches
  reachable.
- HP and potion additions are impossible for every first-battle source and
  never exceed visible max HP, inventory capacity, or the documented
  opportunity bound.
- No transform crosses ascension, overwrites a source record, or replaces the
  visible Act Boss in ordinary training.
- Encounter replacements come solely from authoritative simulator candidates
  and preserve current visible context/history; unsupported cases fail closed.
- Natural, constructed, and paired-counterfactual records remain separately
  countable after serialization and migration.
- Every output preserves source identity, source context, policy version/seed,
  eligibility, requested/actual changes, and native-support gaps.

## Required Verification

Run the standard local gates, focused transform/migration tests, and an audit
over a portable A20 pool containing first and later battles. The task must add
and run a WSL `--lightspeed-constructed-battle-start-audit` command that reports
per-transform eligibility, trigger/no-op/actual counts, source/constructed
counts, cap violations, and unsupported native operations. Its PR report must
include the pool provenance, transform-policy configuration, exact command,
and all visible-context assumptions.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_battle_start_transform.patch
src/sts_combat_rl/sim/expert_iteration.py
tests/test_expert_iteration.py
```

The legacy practical HP direction may inform the implementation, but it lacks
the current public-context, provenance, and distribution-separation contracts.
Do not copy it wholesale.

## PR Report

Include task ID, artifact/policy versions, source pool and context coverage,
transform counts by kind, all no-op/unsupported reasons, exact verification,
legacy files consulted, known limitations, and any unmet acceptance criterion.
