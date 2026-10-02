# T112 preparation and bounded execution workflow

This is the STSRL-owned artifact workflow for T112 / PR #130. It is not an
execution approval. The implementation is bound to contract commit
`bd7a04a25bce2677c8dcf6a5e1c03751b43de90f`, the current clean T112 branch
head, and native integration pin
`6496fc1c7e629a374b72bd94f7fd29afe29c7f62`.

## Stage 0: qualify inputs without native execution

Run `prepare` only from the clean `planner/t112-sampler-seed-repair-cohort-recovery`
worktree and a fresh artifact directory:

```powershell
python -m sts_combat_rl.commands.t112_sampler_seed_recovery_cli prepare `
  --t101-retention-manifest <T101-retention-manifest.json> `
  --t111-retention-manifest <T111-retention-manifest.json> `
  --native-source-manifest <current-sts-lightspeed-source-manifest.json> `
  --artifact-root <new-T112-preparation-directory> `
  --repo-root <T112-worktree>
```

This stage does not import the native module or call the simulator. It
revalidates the complete 413-row T101/T111 provenance and the current native
source manifest, and emits a T112 input qualification, readiness preparation,
and preparation retention manifest. Preparation records that all 413 T111
candidate rows have null `bridge_report_sha256`; their raw reports are
ineligible for reuse. Historical T111 exclusion labels are never admissions.
It also retains a `t112-validator-repair-provenance-v1` artifact spelling out
the corrected bridge-input/per-particle seed invariants and the unchanged
strict-schema, type/index, support, and historical-artifact boundaries.

## Stage 1: separately authorized one-call native witness

Before the witness, a Maintainer must publish a distinct exact-head approval
and create a `t112-maintainer-stage-authorization-v1` document with
`stage=witness`, decision `N2_NATIVE_WITNESS_AUTHORIZED`, its approval comment
ID, the preparation artifact paths/hashes, exact native source manifest and
binary path/SHA/size, and a one-worker `[0,1)` resource plan. The resource
guard plan binds the exact status path, resource root, batch/job IDs, aggregate
budget, memory request, runtime RSS cap, MemAvailable floor, and sample
interval. The validator checks the live exact branch/head, clean worktree,
binary hash and ABI, and resource plan before execution.

Launch only the witness command under the repository's detached-job and
resource-lease convention. For example, pass this command vector to
`scripts/run_detached_job.py start` after creating the approved guard status
path and supplying the matching resource arguments:

```text
python -m sts_combat_rl.commands.t112_sampler_seed_recovery_cli witness
  --authorization <witness-authorization.json>
  --qualification <t112-input-qualification.json>
  --readiness <t112-readiness-preparation.json>
  --resource-status <witness-resource-status.json>
  --t101-retention-manifest <T101-retention-manifest.json>
  --output-root <new-witness-output-directory>
  --repo-root <T112-worktree>
```

The witness restores the deterministic first A-stratum identity in the
already-qualified T101 selector order, derives its unchanged T101 bridge seed,
and invokes the strict T111 native record runner once. It validates the actual
report with the corrected strict validator, retains only bridge-input and
indexed per-particle seed metadata plus report hash, and never enters the
candidate selector. `finalize-witness` verifies the completed resource guard
and emits the witness terminal. Candidate execution remains blocked unless
that terminal is `ACCEPTED` with exactly one bridge call and zero retries.

## Stage 2: separately authorized bounded cohort

After successful witness finalization, obtain a separate exact-head approval
and a new `stage=cohort` authorization, decision
`BOUNDED_COHORT_EXECUTION_AUTHORIZED`. Bind the same T112 head, spec commit,
native source manifest and binary, input qualification/readiness, accepted
witness terminal, and a one-worker `[0,413)` resource guard with exact
stratum ranges A `[0,93)`, B `[93,285)`, C `[285,413)`. The authorization
validator rejects any missing or changed witness, approval, source, binary,
head, or resource binding.

Run the CLI's `execute` command under the detached resource guard. It reloads
the qualified exact T101 source population, reuses T111's strict validator,
deterministic per-stratum hash ordering, and no-retry record runner, and calls
the native bridge exactly once for each attempted candidate. It stops each
stratum on its eighth admission or exhaustion. A pre-bridge failure cannot be
reported as a completed candidate exclusion because the T112 attempt schema
requires one observed bridge call per attempt. No report from the old T111
attempt is read as admission evidence.

## Finalization and terminal vocabulary

Run `finalize` only after the detached guard is terminal and successful. It
rechecks the guard, the witness gate, exact T112 authorization/provenance,
attempt JSONL/cohort identity, and all artifact hashes, then emits a T112 final
report and retention manifest with direct references to the T112 outputs and
the qualified T101/T111/native inputs.

The only T112 scientific terminal values are:

- `SAMPLER_SEED_CONTRACT_REPAIR_INVALID` (the witness failed its contract);
- `CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED`;
- `CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT`.

Missing, interrupted, contradictory, or unverified evidence is `INCOMPLETE`,
not a scientific terminal. This implementation does not authorize executing
any stage: Maintainer review and exact-head, stage-specific readiness/resource
approval are still required. It does not run native builds, witnesses,
candidate calls, convergence, or training by itself.
