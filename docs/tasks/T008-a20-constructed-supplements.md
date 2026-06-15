# T008: A20 Constructed Battle Supplements

Status: `BLOCKED` by T003 and T004.

## Objective

Add conservative, seeded, explicitly tagged A20 battle-start supplements
without pretending they are natural states.

## Scope

- Implement same-A20 small current-HP bonuses as approximate constructed data.
- Use a versioned seeded proposal that does not trigger on every sample.
- Disable HP and potion additions before the first battle.
- Cap HP additions by missing HP and a documented small policy cap; favor small
  deltas.
- Add simulator-native random potions with conservative opportunity bounds.
- Add authoritative same-structure legal ordinary/elite encounter replacement.
- Preserve source checkpoint, eligibility, trigger, requested changes, actual
  changes, and distribution tags.
- Keep a natural-source core in any training mixture.

## Out Of Scope

- Mandatory replay certificates for every small HP change.
- A0-to-A20 reconstruction.
- Boss replacement in ordinary training.
- Claims that constructed data replaces natural A20 coverage or evaluation.

## Acceptance Criteria

- Only actual modifications receive constructed-data tags.
- First-battle additions are impossible.
- Proposal decisions are seeded and reproducible but stochastic across seeds.
- Natural, constructed, and paired-counterfactual outputs remain separate.
- Boss replacement exists only as paired counterfactual evaluation if included.
- Required local and WSL transform audits pass.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_battle_start_transform.patch
src/sts_combat_rl/sim/expert_iteration.py
tests/test_expert_iteration.py
```

The legacy practical HP policy is preferable to the older mandatory-certificate
path, but the PR must remain focused and independently reviewed.
