# T007 Review Handoff

Date: 2026-06-22.

This is the current handoff record for the next main maintainer. It reviews
the clean `main` baseline and the unmerged T007 implementation attempt. It is
not evidence that public run context is implemented.

## Decision

PR #9, `Add public run context schema and pipeline integration`, was closed
without merge on 2026-06-22. Its branch head remains reachable as a read-only
research reference. Do not continue work on its existing branch.

The implementation reference is:

- PR: `https://github.com/lsmfttb/STSRL/pull/9`
- Branch: `claude/suspicious-jackson-e13378`
- Head: `bdfd5e09e2b36e7b9e069bb116ca3cac9fa9b334`
- Main review base: `155077f6ce07017a11197683c668a7833d8e203f`
- Scope: 20 commits, 20 files, 4,221 insertions, and 28 deletions.

Repeated patch regeneration and cross-cutting revisions mean that another
round on this branch would be less reliable than new focused tasks from
`main`. Do not delete the remote branch immediately; its design ideas and
tests can be consulted while replacement tasks are written.

## Main Baseline

`main` is clean at `155077f` (`Update T005 completion documentation`). It has
T001-T005, T010, T011, and T013: controlled runs, portable battle-start pools,
fixed structural evaluation, the stochastic non-combat driver, tactical-v2
features, and the CommunicationMod adapter. It does not have a sanitized full
public run context or complete public run history.

Windows verification on 2026-06-22 passed with checkout sources on the module
path:

```powershell
$env:PYTHONPATH = 'src'
pytest                              # 407 passed
python -m compileall -q src tests   # passed
ruff check src tests                # passed
ruff format --check src tests       # 75 files already formatted
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

The mock commands emitted `play 1 0` and `end`. In a bare checkout, direct
CLI commands need either `PYTHONPATH=src` or an editable install.

The canonical `main` patch-stack verifier also passed from external
`sts_lightspeed` commit `7476a81`. Direct WSL smoke was not rerun because the
documented external `build-py` shim directory is currently absent. Do not use
the external `build-t007-py` directory as a `main` substitute; rebuild a
canonical `build-py` shim before reporting fresh direct-simulator evidence.

## T007 Findings

### Worth Reusing As Design Direction

- A separate versioned public-context/history contract is the right boundary.
- `execute_controlled_run` is the correct place to append one history entry
  after each successful transition.
- Artifact propagation, explicit missingness, forbidden-field checks, and
  visible map/history replay comparison are necessary directions.

These are not safe cherry-pick candidates. The Python schema, artifacts,
migrations, tests, and native projection share one unaccepted versioned
contract and must be redesigned together.

### Merge Blockers

1. **The submitted native patch does not apply.** An independent clean WSL
   reproduction applied the existing pybind11, step-simulator,
   checkpoint-restore, and battle-start-metadata patches, then failed applying
   `sts_lightspeed_public_run_context.patch` at
   `bindings/slaythespire.cpp:9`. The final PR build claim is not reproducible.

2. **The patch crosses ownership boundaries.** It rewrites the existing
   `LightSpeedAction`, `StepSimulator`, and pybind bindings, changes CMake
   flags, and changes the pybind11 gitlink. These belong to pre-existing patch
   stack layers. A replacement must be generated from the already-applied
   stack and add only public projection fields and required checkpoint state.

3. **Checkpointed encounter history is lost and not compared.** The proposed
   checkpoint struct adds `publicEncounterHistory`, but `captureCheckpoint()`
   constructs it without that vector. Restore therefore receives an empty
   history. The Python context comparer does not compare encounter history, so
   its regression tests cannot catch this.

4. **Persistent resources are absent from the context schema.** The proposed
   top-level object has Boss, encounter/history, and map fields but no current
   HP, max HP, gold, potion inventory, deck, relics, or keys. Per-transition
   deltas cannot reconstruct an arbitrary run without a verified base
   snapshot. This misses T007 scope and blocks T012.

5. **Candidate action semantics are not proved.** The final head moves toward
   `GameAction::getAllActionsInState`, but it also keeps manually constructed
   REST data. Screen rows are not tested against the adapter's
   occurrence-disambiguated legal actions or against selected history actions.

6. **The audit does not discharge its gate.** It counts every earlier history
   entry once per later step, so `20,294` visible screens is a repeated-history
   total, not sampled decision coverage. It neither checks candidate action
   parity nor captures/restores a battle-start record, and `audit_ok` ignores
   collected run problems.

7. **Coverage is insufficient.** The reported three-episode audit saw only
   BATTLE, REWARDS, MAP_SCREEN, EVENT_SCREEN, and CARD_SELECT. It did not see
   SHOP, REST, TREASURE, Boss-relic, or potion-related screens. New screen
   tests are Python dictionaries, not native simulator captures.

8. **Projection and conformance are conflated.** The recursive sanitizer drops
   unknown non-forbidden input keys before validation. That is an acceptable
   output-sanitization operation, but it cannot prove that a native projection
   conforms to the declared schema. The replacement needs separate raw
   conformance and sanitized-output checks.

The final native patch also has trailing whitespace according to
`git diff --check 155077f..bdfd5e0`, despite the PR report claiming otherwise.

## Recommended Replacement Sequence

Do not mark these `READY` until the next maintainer completes a capability
review. They are a proposed split, not published tasks.

1. **Native public projection capability.** On a fresh branch from `main`, make
   the full canonical patch stack apply in a clean worktree. Add only a minimal
   extension to the existing StepSimulator patch. Do not modify CMake,
   submodule gitlinks, or wrapper definitions. Produce a capability matrix for
   map, Boss, persistent resources, each visible screen, and the exact legal
   action source. Checkpoint every newly introduced native field.

2. **Python context and controlled history.** Define the schema after the
   capability matrix. Include a current persistent-resource snapshot, typed
   selected action linked to its pre-decision candidates, screen-specific
   schemas, strict raw-projection conformance tests, and fake-adapter ordering
   tests. Keep artifact format changes out of this task where possible.

3. **Artifact propagation, replay, and audit.** Add sequential migrations and
   propagate the settled schema through manifests, records, batches, and
   cohorts. Replay must compare Boss, map, encounter history, resources,
   history, and candidate actions. The WSL audit must count one current screen
   per decision, report action-set parity and coverage gaps, and fail on run,
   schema, forbidden-field, and replay errors.

T008, T009, and T012 must remain blocked until all required replacement work
merges. Each replacement requires a new branch and PR based on current `main`.

## Next Maintainer Checklist

1. Keep `main` at its clean baseline; do not cherry-pick from closed PR #9.
2. Preserve its remote branch until replacement specifications capture any
   useful reference material.
3. Publish replacement task specifications before authorizing another branch.
4. Rebuild the canonical WSL `build-py` shim before direct simulator work.
5. Update task readiness and current status only after replacement work merges.
