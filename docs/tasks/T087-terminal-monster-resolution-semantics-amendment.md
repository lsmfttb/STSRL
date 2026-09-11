# T087 Terminal Monster Resolution Semantics Amendment

This file is a **normative material amendment** to T087. It supersedes only the terminal-monster count/HP semantics, related dense-diagnostic formulas, and consistency predicates in the existing T087 specification bundle. All cohort, restore, controller, native identity, Search-v2@100, HP-rescue selection, blind-audit role, and historical-input contracts remain unchanged unless explicitly replaced below.

The amendment follows the failed formal natural stage and the Maintainer's bounded replay diagnosis on PR #100. The exact reproduced case was an authoritative `PLAYER_VICTORY` with two retained monster rows: one LOOTER at `current_hp=0, alive=false`, and one MUGGER at `current_hp=29, alive=true`, while `completed_battle_monsters_alive=0`. The accepted native implementation establishes why this is valid: `Monster::isAlive()` is exactly `curHp > 0`; `Monster::isTargetable()` is `!isDeadOrEscaped()`; and the escape path removes the monster from `BattleContext.monstersAlive` without forcing its HP to zero. Therefore row-level HP-alive state and BattleContext active-monster state are distinct concepts and must not be equated.

The retained diagnostic artifact for this diagnosis is:

- `/mnt/d/DeadlyCatCoding/STSRL/artifacts/t087-terminal-telemetry-diagnostic-20260910.json`
- SHA-256 `6ffa60c86e9418a3c1b9474a06c11b4e500c58b40efedbc09afa1a625b0e0667`

The prior four-shard formal natural attempt is rejected in full as scientific evidence. No partial `ROW_PASS` output may be reused. No new canary, formal retry, HP rescue, or downstream audit execution is authorized until this amendment is approved and the implementation is independently reviewed.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: the exact T087 primary task contract and prior normative amendments; exact T085 selected-record/restore/canonical-source identities; current accepted T087 native identity `96052d24b9c2c16ff25b6f7241edd972613be997`; retained terminal monster rows including `current_hp`, `alive`, `targetable`, and `half_dead`; native `completed_battle_monster_count`; native `completed_battle_monsters_alive`; authoritative terminal outcome; and every regenerated T087 natural/dense/HP-rescue/audit/report/retention artifact produced after this amendment.

Reuse mode: `scientific_quality_claim` only inside T087's diagnostic-validity boundary. These semantics are diagnostic definitions, not learned rewards, Search heuristics, policy/value labels, or standalone controller-promotion evidence.

Claim boundary: this amendment establishes how T087 interprets terminal monster state when monsters can be dead, escaped, half-dead, or otherwise removed from Battle resolution while still retaining positive HP. It does not alter native battle mechanics, Search, outcome determination, RNG, reward, cleanup, action execution, or historical T085 results.

Required predicates: exact native terminal monster occurrence list; exact native count/list-length agreement; boolean row `alive`, `targetable`, and `half_dead`; finite non-negative retained HP; native active-monster count consistent with row-level targetability; authoritative terminal outcome; exact controller/native provenance; diagnostic formulas recomputable from retained raw evidence; and all pre-existing T087 source/restore/artifact gates.

Unavailable-fact behavior: any required terminal row, count, targetability value, HP value, outcome, native identity, restore/source binding, or diagnostic provenance that is missing, malformed, conflicting, or inferred from filenames/defaults fails closed to `INCOMPLETE`.

## 1. Freeze the three distinct terminal monster concepts

T087 must distinguish the following concepts.

### 1.1 HP-alive

For a retained monster row:

```text
hp_alive := row.alive
```

The accepted native meaning is `Monster::isAlive()`, exactly `curHp > 0`.

`hp_alive=true` does **not** imply that the monster is still an unresolved Battle participant. In particular, an escaped monster may retain positive HP.

### 1.2 Battle-active / unresolved participant

For a retained monster row:

```text
battle_active := row.targetable
```

The accepted native meaning is `Monster::isTargetable()`, exactly `!isDeadOrEscaped()`.

For T087 terminal snapshots, `battle_active` is the row-level observable corresponding to whether the monster still counts as an unresolved targetable Battle participant.

The native scalar:

```text
completed_battle_monsters_alive
```

is therefore interpreted by T087 as the authoritative **Battle-active count**, not the number of rows with `alive=true`.

### 1.3 Retained occurrence

`completed_battle_monsters` is the exact ordered retained native monster occurrence list captured before `exitBattle()`. An occurrence may remain in this list even when it is dead, half-dead, escaped/non-targetable, or otherwise no longer active for Battle resolution.

Accordingly, the following old equality is invalid and must be removed:

```text
completed_battle_monsters_alive == count(row.alive == true)
```

The reproduced escaping-Mugger terminal is a required positive regression for this distinction.

## 2. Terminal telemetry consistency rules

For every terminal T087 row require:

```text
completed_battle_monster_count == len(completed_battle_monsters)
0 <= completed_battle_monsters_alive <= completed_battle_monster_count
completed_battle_monsters_alive == count(row.targetable == true)
```

Every retained monster row must contain:

- occurrence/index identity required by the existing T087/native telemetry contract;
- canonical string monster identity under the existing `id_label` then `name` rule;
- finite `current_hp` and `max_hp` with `current_hp >= 0` and `max_hp > 0`;
- boolean `alive`;
- boolean `targetable`;
- boolean `half_dead`.

Additionally require:

```text
row.targetable == true  => row.alive == true
```

T087 must **not** infer an explicit semantic label such as `escaped=true` solely from `alive=true && targetable=false`. It may retain the descriptive category `non_targetable_hp_alive` because that category is directly supported by the existing fields. No additional native escape flag is required for T087.

## 3. Replace ambiguous terminal count diagnostics

The primary task's old count block:

```text
enemy_count_alive_terminal
enemy_count_killed = enemy_count_initial - enemy_count_alive_terminal
enemy_kill_fraction = enemy_count_killed / enemy_count_initial
```

is superseded. It incorrectly treats every monster removed from Battle resolution as killed and is not valid for escape semantics.

T087 must instead retain at least:

```text
enemy_occurrence_count_terminal = completed_battle_monster_count
enemy_count_active_terminal = completed_battle_monsters_alive
enemy_count_hp_alive_terminal = count(row.alive == true)
enemy_count_non_targetable_hp_alive_terminal =
    count(row.alive == true and row.targetable == false)
```

These are direct observables.

T087 may additionally report:

```text
enemy_count_nonactive_terminal =
    enemy_occurrence_count_terminal - enemy_count_active_terminal
```

but must not call that quantity `killed`.

The old `enemy_count_killed` and `enemy_kill_fraction` fields are removed from required T087 scientific output. If an implementation retains them for backward-compatible debugging, they must be explicitly marked non-authoritative/unavailable whenever removal-from-Battle cannot be proven to equal death from retained evidence. They may not participate in READY or audit selection.

## 4. Freeze terminal enemy-HP semantics

T087 must retain two HP totals because they answer different questions.

### 4.1 Raw retained HP

```text
terminal_total_enemy_hp_all_occurrences =
    sum(max(0, row.current_hp) for every retained terminal occurrence)
```

This preserves actual HP still present in the retained monster objects, including positive HP on non-targetable/escaped occurrences.

### 4.2 Battle-active unresolved HP

```text
terminal_total_enemy_hp_active =
    sum(max(0, row.current_hp) for rows where row.targetable == true)
```

This is the T087 quantity used for the question "how much enemy HP remains unresolved in the Battle at player death?"

For authoritative `PLAYER_LOSS`, redefine the required loss-side ratio as:

```text
enemy_hp_remaining_fraction =
    terminal_total_enemy_hp_active / battle_start_total_enemy_hp
```

and define:

```text
enemy_hp_progress_fraction_v1 = 1 - enemy_hp_remaining_fraction
```

The old required name `enemy_damage_fraction` is superseded because escape, summoning, healing, phase mechanics, or other Battle-resolution behavior can make `1 - remaining/entry` differ from literal damage dealt.

The raw all-occurrence HP total must still be retained so later analysis can distinguish "enemy removed from Battle with HP left" from "enemy HP actually reduced to zero".

## 5. Range semantics and dynamic encounters

The previous requirement that `enemy_hp_remaining_fraction` and its complement must always lie in `[0,1]` is superseded.

Require only:

```text
battle_start_total_enemy_hp > 0
enemy_hp_remaining_fraction is finite and >= 0
enemy_hp_progress_fraction_v1 is finite
```

Do not clip either value.

A value of `enemy_hp_remaining_fraction > 1` is not automatically invalid because later native mechanics may introduce additional active HP through summons, healing, phase transitions, or other encounter behavior. The retained raw entry/terminal occurrence and HP evidence must explain the value. If the required raw evidence is internally inconsistent, fail closed; do not force the scalar into `[0,1]`.

This amendment does not attempt to build a global causal attribution of damage, summoning, healing, or escape. Its purpose is to retain enough decomposed evidence that those mechanisms are not silently collapsed into a misleading bounded scalar.

## 6. Signed terminal margin

The win-side definition remains unchanged:

```text
combat_terminal_margin_v1 =
    + player_hp_remaining_fraction_of_max
```

For `PLAYER_LOSS`, redefine exactly:

```text
combat_terminal_margin_v1 =
    - enemy_hp_remaining_fraction
```

where `enemy_hp_remaining_fraction` now uses **Battle-active unresolved HP only** as defined above.

The loss-side margin is therefore finite and non-positive but is no longer required to be >= -1.

This remains a diagnostic scalar only. The decomposed raw fields are authoritative.

## 7. Blind-audit semantics

The existing blind-audit threshold schedule remains unchanged and applies to the amended active-unresolved definition of `enemy_hp_remaining_fraction`:

- near-boundary losses: first sufficient threshold from `0.25, 0.35, 0.50, 0.65, 0.75, 1.00` using `<=`;
- deep losses: after excluding selected near losses, first sufficient threshold from `0.75, 0.65, 0.50, 0.35, 0.25, 0.00` using `>=`.

A loss ratio above 1 remains eligible for the deep-loss stratum.

Human-review traces should expose player-visible escape/retreat consequences where they are already present in the ordinary visible action/state log, but must not expose hidden native flags or internal Search telemetry.

## 8. HP-rescue semantics

HP-rescue selection remains outcome-blind with respect to dense magnitude except for the already-approved requirement that candidates are natural `PLAYER_LOSS` records. The exact SHA ranking and 8/8/8 cohort quotas remain unchanged.

Every HP-rescue variant must compute its terminal margin using the amended active-unresolved HP definition. The natural-row validation required before HP-rescue selection must use this amendment.

No previously generated partial formal natural row may seed HP-rescue selection.

## 9. Native-change boundary

No further native change is required by this amendment.

The existing accepted native identity:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 96052d24b9c2c16ff25b6f7241edd972613be997`

already exposes all required fields:

- `completed_battle_monster_count`;
- `completed_battle_monsters_alive`;
- ordered `completed_battle_monsters` rows;
- row `current_hp` / `max_hp`;
- row `alive`;
- row `targetable`;
- row `half_dead`.

Do not add a new `escaped` field merely for T087. If implementation discovers a case where the existing `targetable` surface does not correspond to native Battle-active membership at the terminal capture boundary, stop and return to Planner before changing native semantics or telemetry.

## 10. Required implementation regressions

Before any new canary, require focused tests covering at least:

1. the reproduced victory with `completed_battle_monsters_alive=0` and a positive-HP non-targetable MUGGER is accepted;
2. `count(row.alive)` is explicitly allowed to differ from `completed_battle_monsters_alive`;
3. `count(row.targetable)` must equal `completed_battle_monsters_alive`;
4. a targetable row with `alive=false` fails closed;
5. monster count/list-length mismatch fails closed;
6. missing/non-boolean `targetable`, `alive`, or `half_dead` fails closed;
7. loss-side remaining HP sums only targetable rows while the raw all-occurrence HP sum retains positive HP on non-targetable rows;
8. a valid loss-side remaining fraction above 1 is retained rather than clipped or rejected solely for range;
9. old `enemy_count_killed`/`enemy_kill_fraction` cannot satisfy READY as authoritative required fields;
10. blind-audit and HP-rescue terminal-margin recomputation use the amended active-unresolved definition.

## 11. Execution reset

The failed formal attempt at implementation head `55ad01de130bf8d82dada2a00e015435223ba6de` is not reusable evidence.

After Maintainer approves the exact spec head containing this amendment and independently accepts the implementation repair:

1. rerun a bounded canary that must include the reproduced escaping-Mugger record in addition to ordinary win/loss coverage;
2. independently review that canary;
3. only then authorize a fresh 413-record natural formal stage from the beginning;
4. no partial row or shard from the failed formal attempt may be merged into the new run.

The terminal classes remain unchanged: `DENSE_COMBAT_DIAGNOSTICS_READY` only after all amended T087 predicates pass; otherwise `INCOMPLETE`.