# T052: T051 Boss/Later-Act Fixed-Cohort Diagnostic

## Objective

Build an immutable restored-battle diagnostic cohort from the accepted T051
Boss and later-act natural battle starts, then compare the current search arms
on those exact starts at equal native root budget.

This task answers whether the scarce T051 later-act reachability signal is
useful restored-battle evidence before any broad teacher/checkpoint refresh,
assisted training repair, non-combat ranker branch, or controller promotion.
It is still `full_simulator_state_oracle_like` diagnostic evidence only.

## Current Main Baseline

T051 is complete. Its accepted retained artifact root is:

```text
artifacts/t051-search-controlled-later-act-source-collection-pr/
```

The retained T051 manifest sha256 is
`e2c83ef4892ff74129c3649dc4b1dd52493777b74339f094c5c804e2bbb3d0b9`, and the
reachability report sha256 is
`0e001e38b3a7587dd7f1845a6d3fcfc6541f2056dffd8e4aaa5206053adc3877`.

T051 ran 1,000 terminal A20 source runs per arm with matched seeds `1..1000`,
step cap 500, search budget 20, root selection `highest_mean`,
`stochastic-v1` non-combat control with seed 42050, and 16 source and
coverage/restore workers per arm. The accepted result was:

- baseline `oracle_search_v1`: 4,774 battle starts, 32 Act-1 Boss starts, no
  Act-2+ starts;
- `model_guided_oracle_search_v2`: 4,771 battle starts, 34 Act-1 Boss starts,
  3 Act-2+ starts from 1 source run;
- `root_prior_guided_oracle_search_v1`: 4,548 battle starts, 22 Act-1 Boss
  starts, 2 Act-2+ starts from 1 source run.

The T009 broad-training gate remained closed. T051 therefore recovered a small
later-act source signal, but it did not create broad A20 training readiness or
controller-promotion evidence.

## Dependencies

- T051 retained source artifacts and reachability evidence.
- T050 source-pool merge/finalization and coverage merge support.
- T048 checkpoint provenance for the checkpoint-guided arms.
- T047 root-prior guided restored-battle comparison workflow.
- T005 fixed-cohort and restored-battle evaluation contracts.

## Inputs And Artifacts

Required T051 inputs:

- retained root:
  `artifacts/t051-search-controlled-later-act-source-collection-pr/`;
- T051 retention manifest sha256
  `e2c83ef4892ff74129c3649dc4b1dd52493777b74339f094c5c804e2bbb3d0b9`;
- T051 reachability report sha256
  `0e001e38b3a7587dd7f1845a6d3fcfc6541f2056dffd8e4aaa5206053adc3877`;
- baseline merged pool sha256
  `1d52a2a3027347b88bb75f28b5fbe1a8f7f01f028d80594d252325a24d6ab3b1`;
- post-search merged pool sha256
  `71061152efeef70a8b136f3abc4d1f8e89636d1c776b6f05fcd37617232f146c`;
- root-prior merged pool sha256
  `ca8d4a81caa2b446bb753ddb7e473aa7d9b5d3b0831408c4f9d3693b9ea89d48`;
- checkpoint sha256
  `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`.

Generated T052 artifacts must remain under an ignored stable path such as:

```text
artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/
```

The PR must write a lightweight retention manifest naming generated cohort,
comparison, log, and summary artifacts with paths, schema ids, record counts,
byte counts where practical, SHA-256 hashes, commands, worker/shard counts,
runtime provenance, retention reason, downstream consumers, and deletion
conditions.

## Scope

- Verify the required T051 hashes and source configuration before consuming
  the retained artifacts.
- Build one immutable fixed diagnostic cohort from T051 natural starts:
  - include every Act-2+ battle start from the T051 post-search and root-prior
    guided arms;
  - include every Act-1 Boss start from all three T051 arms unless a documented
    restore/tooling failure forces an explicit omission;
  - preserve each record's original T051 source arm label, source checkpoint,
    source run id, battle index, controller provenance, public-context status,
    structured-outcome status, and information regime.
- Deduplicate only exact duplicate source checkpoint identities. Do not
  balance, score, hand-filter, construct, or replace states by perceived deck,
  relic, path, or winnability quality.
- Run the required restored-battle comparison arms on the identical cohort:
  - baseline `oracle_search_v1`;
  - `model_guided_oracle_search_v2`;
  - `root_prior_guided_oracle_search_v1`.
- Use equal native root budget 20 and root selection `highest_mean` where
  applicable. Use the same T048/T051-compatible checkpoint for checkpoint
  guided arms.
- Report overall, Boss-only, and Act-2+ subset outcomes separately, including
  battle win/death, terminal HP, structured resource status, restore failures,
  controller failures, root-mapping/allocation failures, model calls, native
  simulator steps, and wall-clock cost.
- State whether root-prior guided search improved, tied, or regressed versus
  both baseline Oracle search and post-search model-guided search on this
  fixed diagnostic cohort.

## Out Of Scope

- New source collection.
- New teacher datasets, trainer inputs, checkpoints, calibration reports, or
  broad A20 training.
- Non-combat driver changes or non-combat ranker work.
- Controller promotion, live-game validation, natural A20 performance claims,
  normal-information claims, or final-agent claims.
- Constructed battle starts, hand-authored local Slay the Spire mechanics, or
  replacing visible Boss information.

## Design Constraints

- All compared search arms remain `full_simulator_state_oracle_like`.
- The cohort is a diagnostic fixed-evaluation artifact, not a natural-run
  performance distribution and not a training distribution.
- The cohort must retain source-arm provenance so T051 reachability and T052
  restored-battle results are not conflated.
- Missing Boss or later-act records must be reported as zero or omitted with
  explicit failure provenance; do not fill gaps with constructed or
  counterfactual states.
- Large or long-running WSL restored-evaluation stages must use explicit
  shards and workers. On the current 16-logical-core maintainer machine, use
  16 workers by default unless the PR reports a concrete resource or tooling
  reason for fewer.

## Deliverables

- A deterministic cohort extraction path or script for the T051 Boss/later-act
  diagnostic cohort, plus focused tests if new code is added.
- A current-schema fixed cohort artifact and cohort summary.
- A root-prior guided search comparison report over the cohort, with hashes and
  a concise formatted summary.
- A retention manifest for the T052 artifact root.
- PR evidence comparing T052 results with T048 fixed-cohort evidence and T051
  complete-run reachability evidence.

## Acceptance Criteria

- Required T051 input hashes are verified before the cohort is built.
- The cohort includes all T051 Act-2+ starts from post-search and root-prior
  arms and all T051 Act-1 Boss starts from the three required arms, unless any
  omission is explicitly reported with a restore/tooling reason.
- Every cohort record preserves original T051 source identity, source-arm
  label, battle and non-combat controller provenance, public-context status,
  structured-outcome status, action trace identity, and information regime.
- Required comparison arms use the same cohort, same action-space
  configuration, equal native root budget, same root-selection rule where
  applicable, and the same checkpoint for checkpoint-guided arms.
- Restore, source/cohort mismatch, malformed provenance, hidden-field leakage,
  controller, root-mapping, and allocation failures fail closed or are reported
  as explicit per-record failures with aggregate command status.
- Results are separated into overall, Act-1 Boss, and Act-2+ subsets.
- The PR states exactly one recommended next task.
- No broad-training, controller-promotion, natural A20 performance,
  normal-information, live-game, or final-agent claim is made.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-doc checks, and
`git diff --check`. If code changes are made, run focused tests for the new
cohort extraction, manifest, or comparison paths.

Run the same-runtime PyTorch/native probe from
`docs/sts_lightspeed_wsl_spike.md` with the exact Python interpreter and
`slaythespire` build path used for restored-battle comparison.

Run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run the restored-battle comparison through WSL on explicitly reported artifact
paths. The PR must include exact commands, shard/worker counts, cohort record
ranges, wall-clock cost, output paths, hashes, and any lower-worker reason.

## Legacy Reference

Consult T005 for fixed-cohort schema and restore semantics, T047/T048 for the
root-prior guided comparison report, T050 for merged source-pool artifact
contracts, and T051 for the accepted retained source artifacts. Do not port
unrelated legacy search, local mechanics, training, or non-combat code.

## PR Report

The PR must report task ID, verified T051 input hashes, cohort extraction
rules, cohort identity and counts by source arm/act/room/encounter, checkpoint
identity, source manifest identity, comparison arms, budgets, root-selection
rules, action-space configuration, exact WSL runtime, commands, worker/shard
counts, wall-clock costs, artifact paths and SHA-256 hashes, restored-battle
outcomes by overall/Boss/Act-2+ subsets, failure counts, comparison with T048
and T051 evidence, exactly one recommended next task, verification results,
known limitations, documentation impact, and every unmet acceptance criterion.
