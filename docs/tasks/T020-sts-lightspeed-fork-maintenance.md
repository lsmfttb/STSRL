# T020: sts_lightspeed Fork Maintenance Line

Status: `READY`.

## Objective

Turn the STSRL `sts_lightspeed` fork from a set of task-shaped useful branches
into one clearly documented active integration line.

The result should remove ambiguity about which fork branch maintainers and
implementers should build from, while preserving exact-commit reproducibility
through the STSRL source manifest.

## Current Main Baseline

T017 replaced the old day-to-day patch-stack workflow with a pinned external
source manifest and verifier. Current `main` records:

- upstream repository: `https://github.com/gamerpuppy/sts_lightspeed.git`
- upstream base commit: `7476a81954020087da31d41d16fddf475746ec2d`
- integration repository: `https://github.com/lsmfttb/sts_lightspeed.git`
- integration ref: `refs/heads/stsrl/t008-constructed-battle-start-v1`
- integration commit: `e9f0e7f104ea2bd908ba5b8f6528c240e6c92ad9`

The fork currently also has historical STSRL task branches such as
`stsrl/t006-oracle-search-teacher-v1`, `stsrl/t017-current-native-surface-v1`,
and `stsrl/t018-terminal-resource-identity-v1`. They are useful provenance, but
they should not all be treated as active integration branches.

After this task was published, fork-side maintenance issues STSRL-001--003
advanced `stsrl/main` to
`242344c57c17c784708a6f072c905febc3f96527`. The delta from the old T008
source commit to that active-branch commit is maintenance-only: fork
documentation, native-change templates, an API smoke script, and `.gitignore`.
It does not change native game code, pybind behavior, or STSRL's native
capability contract.

## Dependencies

- T017 is complete.
- T006, T008, T012, T014, T016, and T018 provide the current native capability
  inventory represented by the pinned commit.

## Scope

- Create or identify exactly one active fork integration branch for STSRL,
  named `stsrl/main` unless the PR justifies a better stable name.
- Point that branch at the accepted maintenance-line commit
  `242344c57c17c784708a6f072c905febc3f96527` without changing native game code
  or pybind behavior.
- Update `docs/sts_lightspeed_source_manifest.json` so its integration branch
  and ref use the new active integration branch while pinning the exact
  active-branch commit.
- Update WSL operations documentation so day-to-day verify/rebuild commands
  fetch the active integration branch, not an old task branch.
- Document fork maintenance policy in STSRL docs: one active integration
  branch, exact commits pinned by manifest, historical task branches retained
  only as provenance, and future native tasks developed on temporary branches
  before advancing the active line through a reviewed STSRL PR.
- Optionally add immutable tags in the fork for accepted STSRL source states,
  but do not make tags the only build input. The STSRL manifest remains the
  authority.
- Keep the old task branches available unless the main maintainer separately
  approves branch deletion.

## Out Of Scope

- Changing native `sts_lightspeed` code or adding new native APIs.
- Rebasing onto a newer upstream commit.
- Deleting historical fork branches.
- Reopening the retired STSRL patch-stack workflow.
- Changing Python adapter behavior, artifact schemas, controller behavior,
  training behavior, search behavior, or evaluation claims.
- Turning `sts_lightspeed` into a checked-in submodule or vendored dependency.

## Design Constraints

- The final game remains the mechanism authority. The fork only exposes native
  simulator surfaces required by STSRL.
- STSRL must depend on exact commits recorded in the manifest, not on whatever
  a moving branch happens to contain.
- The active integration branch is a human-friendly entrypoint; the manifest
  commit remains the reproducibility contract.
- The canonical verifier must continue to use a disposable worktree and must
  fail on wrong commits or missing required native APIs.
- WSL runtime gates must continue to report source identity: upstream/base
  commit, integration ref/commit, manifest version, capability inventory, and
  verifier command.
- No local, unrecorded fork branch state may be required for STSRL gates.

## Deliverables

- Fork-side active branch `stsrl/main` at
  `242344c57c17c784708a6f072c905febc3f96527`, or an equivalent stable branch
  name justified in the PR.
- Updated `docs/sts_lightspeed_source_manifest.json` pointing at the active
  branch/ref and exact active-branch commit.
- Updated WSL operations documentation and current-status wording that explain
  the active branch and historical branch disposition.
- Tests or verifier checks proving the manifest still parses and the expected
  source identity still reports correctly.
- PR report containing the exact fork commands used to create/update the
  active branch and any tags.

## Acceptance Criteria

- There is exactly one documented active STSRL fork integration branch.
- The source manifest points to that active branch and still pins commit
  `242344c57c17c784708a6f072c905febc3f96527`.
- The canonical source verifier succeeds from a clean/disposable checkout.
- The old task-shaped fork branches are documented as historical provenance,
  not as recommended build inputs.
- No native game code, pybind behavior, adapter behavior, artifact schema, or
  controller behavior is changed.
- WSL documentation no longer tells maintainers to fetch the old T008 task
  branch for normal rebuilds.

## Required Verification

Run the standard local gates from `tasks/README.md`, plus focused source
manifest tests:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Run the canonical WSL source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

If the local system `build-py` is rebuilt or touched, also run the standard WSL
smoke and battle-training-readiness gates and report the exact rebuild command.

## Legacy Reference

Use T017 and `docs/sts_lightspeed_wsl_spike.md` as the maintenance baseline.
The old ordered patch-stack verifier remains retired provenance only.

## PR Report

The pull request must include:

- task ID and link to this document;
- exact fork commands used to create or update the active integration branch;
- old and new source manifest identity text;
- fork-side delta summary from the previous pinned source commit to the new
  active-branch commit;
- verifier output summary;
- whether any fork tags were created;
- confirmation that old task branches were not deleted unless separately
  approved;
- exact local and WSL verification commands and results.
