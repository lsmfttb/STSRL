# T017: Stable sts_lightspeed Source Integration

Status: `DONE`.

## Objective

Replace the current day-to-day ordered `sts_lightspeed` patch-stack workflow
with a pinned, reproducible external source integration that future native
surface tasks can extend without growing a fragile local patch queue.

This is a maintenance and provenance task. It does not change Slay the Spire
mechanics, training semantics, controller behavior, or evaluation claims.

## Current Main Baseline

`main` stores Python adapters, WSL commands, and an ordered set of local
patches under `patches/`. `scripts/verify_lightspeed_patch_stack.sh` applies
that stack to external `sts_lightspeed` commit `7476a81` in a disposable
worktree and proves the current native API builds.

That workflow is reproducible, but it is becoming an awkward integration line:
T006, T008, and T012 are all expected to add or depend on additional native
surface area. Extending the local patch queue before stabilizing simulator
source maintenance would make later review, rebuilds, and conflict resolution
unnecessarily expensive.

The authoritative simulator checkout remains outside this repository at
`~/stsrl-spikes/sts_lightspeed`, and real simulator gates still run through WSL.

## Dependencies

- T004, T010, T014, and T016 are complete.
- T006, T008, and T012 must wait for this task before adding new native
  simulator surface.

## Scope

- Define one canonical external `sts_lightspeed` source integration for STSRL,
  preferably a pinned fork branch or equivalent pinned external Git reference.
  The source itself must stay outside this repository.
- Add a versioned repository-owned source manifest at
  `docs/sts_lightspeed_source_manifest.json` that records, at minimum,
  upstream repository URL, integration repository or remote URL, base commit,
  integration commit, branch/ref name, expected Python module name, supported
  native capabilities, and the current STSRL task provenance for those native
  capabilities.
- Add a verifier script, `scripts/verify_lightspeed_source.sh`, that reads the
  manifest, checks out the pinned source in a disposable worktree, initializes
  required submodules, builds the Python module, and asserts the native API
  capabilities required by current `main`.
- Keep or archive the existing patch files as reviewable provenance, but make
  the new source manifest and verifier the canonical path for future native
  work. Future tasks must not append ad hoc patches to the retired ordered
  stack unless a later task explicitly reopens that workflow.
- Update WSL operations documentation and current-status wording so maintainers
  know how to verify, rebuild, and report the pinned integration source.
- Ensure current simulator provenance reports can name the new source identity
  unambiguously. This may be a small shared helper or structured constants, but
  it must not alter decision semantics.
- Rebuild the local WSL `build-py` used by runtime gates from the accepted
  pinned source and document the exact rebuild command in the PR report.

## Out Of Scope

- Adding Oracle search, battle-start transforms, structured resource outcome
  fields, or any other new simulator capability beyond the native API already
  required by current `main`.
- Reimplementing game mechanics in Python or changing legal-action,
  checkpoint, projection, or non-combat behavior.
- Vendoring game files, simulator binaries, jars, save files, or large build
  artifacts into this repository.
- Turning `sts_lightspeed` into a required checked-in submodule.
- Claiming real-game or A20 policy-strength improvement.

## Design Constraints

- The final game remains the mechanism authority. `sts_lightspeed` is the
  current large-scale simulation substrate, not a second game specification.
- Every WSL result must name the pinned source identity: upstream/base commit,
  integration ref/commit, manifest version, and verifier result.
- The verifier must be reproducible from a clean external checkout and must use
  a disposable worktree. It must not silently mutate the user's system
  `build-py`, push commits, or rely on an unrecorded local branch state.
- Current native capabilities must remain available: step simulation,
  checkpoint capture/restore, battle-start metadata, accepted run potion
  fields, non-combat potion actions, GCC 15 build compatibility, and native
  public projection.
- Existing artifact schemas and migrations remain unchanged except for
  explicit simulator-source provenance wording if needed.
- Future native-heavy tasks, including T006, T008, and T012, must extend the
  pinned source integration rather than revive an unmanaged patch-stack branch.

## Deliverables

- Versioned `docs/sts_lightspeed_source_manifest.json` source manifest.
- `scripts/verify_lightspeed_source.sh` and focused tests or script checks for
  manifest parsing, required fields, and failure behavior.
- Updated WSL operations documentation naming the new canonical verifier,
  rebuild path, and legacy patch-stack status.
- Updated source-identity/provenance plumbing where current reports still say
  only "patch stack".
- Evidence that current WSL gates pass after rebuilding `build-py` from the
  pinned source.

## Acceptance Criteria

- A clean verifier run builds the pinned source from the manifest and proves
  every current native capability required by `main`.
- The verifier fails nonzero for a missing manifest, missing required field,
  wrong integration commit, build failure, or missing required Python API.
- The old ordered patch-stack verifier is no longer the canonical command in
  current WSL documentation, though it may remain as historical provenance.
- Current Windows local gates and current WSL runtime/audit gates pass with a
  `build-py` rebuilt from the pinned integration source.
- T006, T008, and T012 task documents clearly depend on this task before adding
  further native simulator surface.
- The PR report names the exact source identity and the exact rebuild command
  used for runtime gates.

## Required Verification

Run the standard local gates from `tasks/README.md`, plus focused manifest and
verifier tests, and:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-public-projection-capability-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-public-context-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-training-readiness --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

Before the runtime gates, rebuild `/home/lsmft/stsrl-spikes/sts_lightspeed/build-py`
from the pinned integration source. The PR report must include the exact
rebuild command and confirm the resulting Python module imports from that
directory.

## Legacy Reference

Current patch-stack files are the primary migration reference:

```text
scripts/verify_lightspeed_patch_stack.sh
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
patches/sts_lightspeed_checkpoint_restore.patch
patches/sts_lightspeed_battle_start_metadata.patch
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_non_combat_potion_actions.patch
patches/sts_lightspeed_gcc15_compat.patch
patches/sts_lightspeed_public_projection.patch
```

Use them to prove source equivalence and preserve provenance. Do not broaden
the task by porting legacy search, transform, or resource-outcome patches from
`d56e10e`.

## PR Report

Include task ID, source manifest path and schema version, upstream/base commit,
integration ref/commit, old patch-stack disposition, native capability
inventory, exact verifier output, exact rebuild command, local and WSL gate
results, documentation changes, known risks, and every unmet acceptance
criterion.
