# T014: Native Public Projection Capability

## Objective

Establish a minimal, reproducible native `sts_lightspeed` projection capability
for player-visible run state, and document exactly which fields and screen
actions the simulator can expose without local mechanics reconstruction.

This task is a capability and compatibility boundary. It does not make a
complete public context available to controllers or persisted artifacts.

## Current Main Baseline

The canonical patch stack based on external `sts_lightspeed` commit `7476a81`
builds cleanly. Current snapshots expose tactical battle state plus a limited
set of run fields such as current/max HP, gold, ascension, room type, and
battle-start metadata. Portable checkpoint records explicitly declare
`public_context_status="unavailable"`.

`main` has no native projection for a complete visible map/routes, visible Act
Boss, screen-specific public payloads, an authoritative public persistent
resource snapshot, or a verified source of non-combat candidate actions. The
closed T007 attempt is not a usable patch base.

## Dependencies

- T002, T003, T004, T010, and T011 are complete.

## Scope

- Start from a fresh worktree at external commit `7476a81`, apply the current
  canonical patch stack in its documented order, and generate a focused patch
  from that applied stack only. Do not edit CMake, submodule gitlinks,
  pybind11, `LightSpeedAction`, or existing wrapper definitions.
- Add one versioned raw native public-projection API on `StepSimulator`. Its
  payload must report, for every declared field, either the native
  player-visible value or an explicit `unavailable`/unsupported declaration;
  it must preserve empty versus unavailable where the native source can do so.
- Build and publish a capability matrix covering: visible current-Act Boss;
  complete currently visible map graph, current node, and immediately legal
  routes; current public persistent resources; each observed player-visible
  screen; and the authoritative source used for each candidate legal action.
- For every observed supported screen, demonstrate parity between the native
  projection's candidate actions and the adapter's occurrence-disambiguated
  legal actions. If the simulator lacks a safe source for a screen, report it
  as unsupported rather than constructing actions in Python.
- Checkpoint all newly introduced native state that is not already preserved
  by the existing copied game/battle contexts. Capture/restore tests must
  compare raw projection values, screen identity, and candidate actions.
- Provide a focused command workflow and WSL capability audit. The audit
  counts one current screen per decision, records coverage gaps, and fails on
  projection, candidate-parity, checkpoint, or run errors. CLI code remains
  parsing and routing only.

## Out Of Scope

- Python public-context schemas, sanitizer/allowlist logic, model inputs,
  `DecisionContext` changes, controlled-history recording, artifacts, or
  migrations; T015 and T016 own those concerns.
- Locally reconstructing game mechanics, map edges, screen rows, candidate
  actions, resource identities, or unavailable fields.
- Claiming simulator fields prove an equivalent real-game field. Real-game
  compatibility remains a separate CommunicationMod concern.
- Oracle search, terminal resource labels, constructed states, or model
  training.

## Design Constraints

- The game itself is the ultimate mechanism authority. `sts_lightspeed` is the
  current simulation substrate, and the report must state its external commit,
  applied patch identity, and any known divergence or unavailable field.
- This is a raw native capability surface, not a normal-controller input. It
  must not be passed around as an unrestricted dictionary or treated as a
  sanitized public schema.
- Native code is authoritative for state mutation, screen state, candidate
  actions, map connectivity, resource identity, and checkpoint behavior. Python
  may format/audit values but may not fabricate them.
- The patch must compose with the present canonical stack and leave its
  ownership boundaries intact. New state must have a named capture/restore
  story rather than relying on accidental process-local continuity.
- An unsupported or unobserved screen/field remains explicit in the matrix;
  coverage counts may not be inflated by replaying prior history entries.

## Deliverables

- Focused native patch, canonical-stack build verification, and a versioned
  raw public-projection API.
- Capability-matrix report schema and focused command workflow.
- Native/adaptor candidate-parity and checkpoint-projection tests, including
  explicit unsupported cases.
- WSL audit fixture/report showing observed screen counts, field availability,
  action parity, checkpoint results, and coverage gaps.

## Acceptance Criteria

- The complete canonical patch stack, including this task's focused patch,
  applies and builds from external commit `7476a81` in a clean worktree.
- Each field in the capability matrix names its exact native source and is
  either projected, explicitly unavailable, or explicitly unsupported; no
  value is guessed in Python.
- Every observed supported screen has a candidate-action parity result against
  occurrence-disambiguated adapter actions. Parity failures fail the audit.
- Capture then restore preserves all newly projected fields, screen identity,
  and candidate action identities, or reports a named mismatch.
- The audit counts exactly one current screen per decision and fails on run,
  projection, parity, checkpoint, or schema errors.
- No controller, artifact writer, or normal-information model consumes the raw
  projection in this task.

## Required Verification

Run the standard local gates from `tasks/README.md`, focused native/API/audit
tests, and:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_patch_stack.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-public-projection-capability-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

The PR report must state every observed screen type, unobserved screen type,
field availability, native source, candidate-action parity result, checkpoint
result, external commit, patch-stack identity, and known real-game parity gap.

## Completion Evidence

Merged PR: <https://github.com/lsmfttb/STSRL/pull/10>

Merge commit: `640c8e2`.

The accepted implementation adds `native-public-projection-v1` as a raw native
capability surface on `StepSimulator`, plus
`native-public-projection-capability-report-v1` and the
`--lightspeed-public-projection-capability-audit` gate. The raw projection is
not consumed by controllers, artifact writers, model inputs, or
`DecisionContext`.

Final canonical WSL verification on 2026-06-22 rebuilt
`/home/lsmft/stsrl-spikes/sts_lightspeed/build-py` from external base
`7476a81` plus the verified patch stack and reported:

```text
current decision screens observed: 289
resource snapshot comparisons: 1209
resource snapshot mismatches: 0
candidate-action parity passes: 289
checkpoint projection passes: 289
checkpoint projection failures: 0
audit passed: yes
problems: (none)
```

Observed screen counts were `BATTLE=236`, `CARD_SELECT=2`,
`EVENT_SCREEN=4`, `MAP_SCREEN=16`, and `REWARDS=31`. Coverage gaps remain
explicit for `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and
`TREASURE_ROOM`.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_public_run_context.patch
patches/sts_lightspeed_public_visible_screen.patch
src/sts_combat_rl/sim/public_run_context.py
tests/test_public_run_context.py
```

The closed T007 branch and its patches are research references only. Known
defects include a non-applying patch, changes across existing ownership layers,
lost checkpoint history, incomplete resources, and unproved candidate actions.
Do not cherry-pick or use them as an acceptance reference.

## PR Report

Include task ID, external simulator and patch-stack identity, changed native
surface, capability matrix, observed/unobserved screen coverage, every
field-source and candidate-action parity result, checkpoint evidence, exact
local/WSL results, legacy material consulted, known real-game differences, and
any unmet acceptance criterion.
