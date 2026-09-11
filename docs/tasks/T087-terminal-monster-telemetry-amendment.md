# T087 Terminal Monster Telemetry Amendment

This file is a normative material amendment to T087 and supersedes only the affected native-change and terminal-enemy-evidence portions of:

- `T087-dense-combat-outcome-diagnostics.md`;
- `T087-reproducibility-amendment.md`.

All other approved T087 scientific, cohort, ranking, evaluator, human-audit, and fail-closed rules remain unchanged.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: the exact T087 primary task contract and reproducibility amendment; historical accepted T085 A/B/C selected-record and restore/source identities; native base `d62ff35579b54d70a7428afdf84743c94df3fe0c`; the exact descendant native integration identity produced by this amendment; the transition-only terminal-monster telemetry; and all T087 restore/parity/native-lineage/source-verifier evidence that binds formal execution to that descendant.

Reuse mode: `scientific_quality_claim` only within T087's diagnostic-validity claim. The telemetry may be reused only as raw evidence for T087 terminal monster-state diagnostics under the exact native/provenance contract; it is not a learned target, reward, Search heuristic, mechanics oracle, or independent controller-quality claim.

Claim boundary: this amendment may establish only that authoritative terminal monster state is copied read-only after the terminal action has determined BattleContext outcome and before unchanged `exitBattle`, then exposed as transition-only metadata without changing simulator/Search semantics. It does not establish Battle improvement, modify T085 historical results, or authorize any mechanics/transition/Search change.

Required predicates: exact native base/result lineage; low-risk read-only diff boundary; exact three new completed-battle monster fields plus existing `completed_battle_outcome`; capture before unchanged `bc.exitBattle(gc)` and attach after unchanged cleanup/snapshot path; parity of all pre-existing terminal-transition outputs; unchanged RNG/action/outcome/HP/reward/Search/utility/cleanup semantics; exact transition-only checkpoint-fingerprint key set; clean source verifier; exact 413-record restore/public/legal/source parity under the descendant native identity; and all primary T087 artifact/provenance gates.

Unavailable-fact behavior: any required native identity, lineage fact, copied monster field, occurrence/order/count fact, parity fact, transition-only key, source-verifier result, restore/public/legal/source identity, artifact hash, or provenance field that is missing, malformed, conflicting, inferred, or unavailable fails closed to `INCOMPLETE`. No Python inference, pre-action substitution, replay guess, filename inference, or unauthorized native semantic change may fill the gap.

## Why this amendment is required

Maintainer review of implementation head `fdda10d43f06275572dfb36e194a0473fd8dc30e` established that the accepted `sts_lightspeed` terminal transition does not expose authoritative post-action enemy HP after `BattleContext::exitBattle` clears the active battle context.

The accepted native terminal path is currently equivalent to:

```text
terminal outcome already known in BattleContext
-> capture completed_battle_outcome
-> bc.exitBattle(gc)
-> battleActive = false
-> snapshot()
-> attach completed_battle_outcome
```

Therefore the returned terminal snapshot contains the battle outcome but no authoritative `battle_monsters` / `battle_monster_count`. STSRL has no other accepted post-action/pre-exit surface carrying the missing monster state. Using the pre-action snapshot would be scientifically wrong for T087's loss-distance metric.

T087 must therefore add one narrow read-only terminal telemetry surface rather than infer, replay, or guess terminal monster HP in Python.

## Native change declaration

```text
native_change_required: true
native_risk: low
native_base_ref: refs/heads/stsrl/main
native_base_commit: d62ff35579b54d70a7428afdf84743c94df3fe0c
native_work_branch: work/T087-terminal-monster-telemetry
native_result_ref: refs/heads/stsrl/main
native_result_commit: unavailable until accepted integration
lineage_check: pending
independent_native_review: not-required-by-risk-class; normal independent Maintainer review required
```

Risk classification is **low** because the authorized change is read-only telemetry only. It may copy already-computed terminal BattleContext fields, but it must not alter RNG, action enumeration/execution, outcome determination, HP, rewards, `exitBattle`, screen transitions, Search, utility, backup, or cleanup ordering.

If implementation requires changing any battle/run terminal semantic, transition order, cleanup condition, outcome logic, or Search behavior, this low-risk classification is invalid and affected work must stop for a new high-risk Planner amendment and independent native semantic review.

## Exact native telemetry contract

On a battle step where the native BattleContext has already reached authoritative terminal outcome, capture the following values **after the terminal action has fully updated BattleContext and before calling `bc.exitBattle(gc)`**:

1. `completed_battle_monster_count`
   - exact integer `bc.monsters.monsterCount`;
2. `completed_battle_monsters_alive`
   - exact integer `bc.monsters.monstersAlive`;
3. `completed_battle_monsters`
   - exact ordered `monsterGroupSnapshot(bc)` using the existing accepted per-monster snapshot helper and shape.

The existing `completed_battle_outcome` capture remains unchanged.

After the existing `bc.exitBattle(gc)`, `battleActive=false`, and ordinary `snapshot()` call, attach only those copied values as transition-only metadata to the returned snapshot.

Required field names are exactly:

```text
completed_battle_outcome
completed_battle_monster_count
completed_battle_monsters_alive
completed_battle_monsters
```

No separate mechanics calculation is permitted in Python or C++. The copied monster rows must retain the existing native monster snapshot fields, including ordered occurrence/index and existing string identities (`id_label` / `name`) plus `current_hp`, `max_hp`, `alive`, and other already-emitted monster fields.

T087 consumers must use `id_label` as the preferred canonical string identity when present, then `name` as fallback. A numeric native `id` must not be blindly stringified into a semantic identity.

## Transition-only / checkpoint boundary

The three new `completed_battle_*` monster fields are transition annotations analogous to `completed_battle_outcome`; they are not persistent simulator state and must not become part of checkpoint identity.

After the native integration is accepted, STSRL must update its transition-only checkpoint-fingerprint raw-key contract so the exact transition-only key set includes:

```text
completed_battle_outcome
completed_battle_monster_count
completed_battle_monsters_alive
completed_battle_monsters
```

This update must preserve the T078 principle that restore identity compares persistent/restorable state rather than ephemeral transition annotations.

## Required native verification before integration

Before integrating the temporary native branch into `refs/heads/stsrl/main`, require all of:

1. existing native/build tests pass;
2. a native-shaped regression proves ordinary active-battle `battle_monsters` rows still use the existing shape and string `id_label` / `name` identities;
3. a terminal-loss regression proves the returned post-exit snapshot contains all three copied monster fields plus `completed_battle_outcome`;
4. the copied monster count equals the ordered copied list length;
5. copied `monster_index` values preserve native occurrence order;
6. a terminal-victory regression also exposes the copied fields without changing the authoritative outcome;
7. deterministic parity against `d62ff355...` for the same scripted terminal transitions shows all pre-existing returned fields/outcomes/next-screen/player-resource semantics unchanged; only the newly authorized telemetry keys may differ;
8. no Search/RNG/utility code is changed.

The accepted terminal-transition repair regression around seed `851450` must continue to pass.

## Lineage and manifest gate

After native review:

1. integrate the accepted temporary native branch into `refs/heads/stsrl/main`;
2. record the exact descendant `native_result_commit`;
3. prove `d62ff355...` is an ancestor of that result with `scripts/verify_lightspeed_lineage.sh`;
4. update the STSRL lightspeed source manifest only after integration;
5. run `scripts/verify_lightspeed_source.sh` from a clean source worktree;
6. run affected T078/checkpoint-fingerprint regressions with the new transition-only key set;
7. bind all formal T087 execution to the single new native result identity.

No T087 canary or formal simulator evidence may be retained from `d62ff355...` and mixed with evidence from the repaired telemetry identity.

## Historical T085 artifact boundary

T085 remains scientifically accepted at its historical native execution identity `d62ff35579b54d70a7428afdf84743c94df3fe0c`.

The telemetry-only descendant does not change Search v2, `playoutRandom`, `evaluateEndState`, action semantics, or accepted T085 outcomes. Therefore T085's frozen A/B/C selected-record identities and restore/source artifacts remain historical accepted inputs to T087.

Before T087 execution under the new native identity, all exact 413 selected records must still pass the already-required restore/public-context/legal-action/source-identity parity gates. Any mismatch is `INCOMPLETE`; do not recollect or replace records inside T087.

## T087 implementation repairs still required

This native amendment does not waive the Maintainer's implementation findings at `fdda10d...`.

Before canary/formal execution, the same PR must also fail closed on at least:

- exact T085 selected-record/artifact binding at execution boundaries;
- authoritative source-selection-manifest identity propagation into HP-rescue and blind-audit manifests;
- full READY/classification validation of required artifacts, hashes, native identity, Search API/budget/root rule, action space, restore/source identity, schemas, and HP-rescue provenance;
- native monster identity normalization using accepted string labels rather than numeric `id`;
- raw terminal outcome equality with the retained row outcome;
- recomputation/validation of action and potion-action counts from retained trace evidence;
- rejection of unauthorized HP-transform provenance;
- validation of all natural rows before HP-rescue selection/execution;
- integral accepted HP values/gaps before constructing the frozen rescue ladder.

## Human audit and dense metric boundary

The purpose of this amendment is only to make authoritative terminal enemy state observable. T087's dense metrics remain diagnostic only and may not become a learned reward, Search heuristic, promotion score, or human-label target in this task.

The human-audit bundle remains blind auxiliary evidence only. Human labels remain forbidden as policy/value training targets or sole controller-promotion evidence.

## Re-approval requirement

This is a material contract change because `native_change_required` changes from `false` to `true` and T087's active formal native identity will advance from `d62ff355...` to a new descendant.

No canary/formal execution is authorized until Maintainer re-approves the exact PR head containing this amendment. Ordinary implementation work necessary to prepare the narrow telemetry change may proceed only after that re-approval and must remain inside this amended boundary.
