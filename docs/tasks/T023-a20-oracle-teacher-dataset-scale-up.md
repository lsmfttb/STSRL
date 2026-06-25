# T023: A20 Oracle Teacher Dataset Scale-Up

Status: `DONE` via PR #23, merged 2026-06-25.

## Objective

Add a repeatable, auditable A20 Oracle-like teacher dataset scale-up workflow
that collects a small but structured teacher set for model-guided search work.

The result must answer a narrow question: given a fixed A20 natural
battle-start source set, what teacher data is produced at named native search
budgets, how stable are the selected teacher actions and soft root targets
across those budgets, and what source-coverage limitations remain.

This task is data scale-up and teacher-label quality measurement only. It must
not train a model, implement model-guided search, publish a controller
benchmark, or describe Oracle-like hidden-state search as normal-information
performance.

## Current Main Baseline

Current `main` already has:

- portable natural battle-start pools from T004;
- fixed structural cohorts from T005;
- explicitly `full_simulator_state_oracle_like` teacher collection from T006;
- optional PyTorch policy/value plumbing and broad-training gates from T009;
- structured resource outcomes and public-context artifact propagation from
  T012/T016/T018;
- stable pinned `sts_lightspeed` source integration from T017/T020;
- current-schema A20 coverage reporting from T021;
- current-schema Oracle teacher dataset reporting and source linkage from
  T022.

The current gap is that T006 can collect teacher rows and T022 can audit one
saved teacher JSONL artifact, but there is no single workflow that freezes a
source-selection plan, collects teacher datasets for multiple named budgets on
the same selected A20 starts, emits T022 reports for every budget, and compares
teacher-label stability across budgets before the data feeds model-guided
search work.

## Dependencies

- T004, T005, T006, T009, T012, T016, T017, T018, T020, T021, and T022 are
  complete.
- T007 is cancelled and is not a dependency.

## Scope

- Add a scale-up workflow under `src/sts_combat_rl/commands/` and reusable
  logic below the command layer.
- Add a CLI entry point for A20 Oracle teacher scale-up, for example:

  ```text
  --lightspeed-a20-oracle-teacher-scaleup POOL_JSONL
  ```

- Add focused options for the workflow, for example:

  ```text
  --oracle-teacher-scaleup-output-dir DIR
  --oracle-teacher-scaleup-budgets 20 50 100
  --oracle-teacher-scaleup-source-limit N
  --oracle-teacher-scaleup-seed SEED
  --oracle-teacher-scaleup-coverage-report COVERAGE_JSON
  --oracle-teacher-scaleup-root-selection highest_mean
  ```

  Exact flag names may be adjusted before implementation only by updating this
  task document. The public behavior must remain the same.

- Load one current or migrated A20 natural battle-start source pool.
- Optionally load a T021 coverage report and verify that its natural-pool
  identity matches the source pool.
- Build a deterministic source-selection plan from rule-defined metadata only:

  ```text
  ascension
  act
  room_type
  encounter_id
  source_run_id
  source_checkpoint_id
  ```

- Preserve all selected source identities and source metadata. If a source
  limit is provided, sampling must be seeded, deterministic, and reported.
- Collect Oracle-like teacher JSONL artifacts for each requested native search
  budget on the same selected source starts.
- For each budget, emit a T022
  `oracle-teacher-dataset-report-v1` report linked to the source pool and, when
  provided, the T021 coverage report.
- Emit a current machine-readable scale-up manifest, for example
  `oracle-teacher-scaleup-manifest-v1`, with:

  ```text
  input source identities
  source-selection plan and seed
  selected source coverage by structural metadata
  requested budgets
  generated teacher artifact identities
  generated T022 report identities
  root-selection rule
  native simulator source identity
  information-regime summary
  cross-budget teacher-action agreement
  cross-budget soft-target similarity or explicit unavailability
  problems and warnings
  ```

- Emit a deterministic human-readable stderr summary suitable for PR evidence.
- Keep teacher action labels and soft root-visit targets distinct.
- Keep source coverage separate from teacher rows, root rows, and repeated
  budget tiers.

## Out Of Scope

- Broad PyTorch training or checkpoint promotion.
- Model-guided search controller implementation.
- Fixed A20 benchmark comparison between controllers.
- Normal-information belief search or public-consistent hidden-future
  sampling.
- New `sts_lightspeed` native APIs or native game-code changes.
- Constructed supplement teacher collection unless a future task defines a
  restorable constructed-source teacher boundary.
- Treating repeated budget tiers, repeated teacher decisions, root rows, or
  constructed variants as new natural source coverage.
- Claiming A20 policy strength, live-game readiness, broad-training readiness,
  or normal-information search performance.
- Checking generated teacher datasets, reports, manifests, native artifacts,
  jars, game files, save files, or large binaries into the repository.

## Design Constraints

- The actual game is the final mechanics authority. `sts_lightspeed` remains
  the current large-scale simulator substrate and authoritative simulator for
  this workflow; do not reimplement game mechanics in Python.
- Real simulator collection runs through WSL.
- All generated teacher data in this task is
  `full_simulator_state_oracle_like` and must never be silently reported as
  normal-information evidence.
- Source selection may use only rule-defined metadata. Do not filter or weight
  sources by hand-written judgments about deck quality, relic quality,
  apparent winnability, or route quality.
- The same selected source set must be used for every requested search budget.
- Under-covered A20 strata are expected and should be reported, not hidden.
  Under-coverage alone is not a command failure.
- Malformed source identities, unsupported schemas, mixed or missing
  information-regime provenance, T021 source identity mismatches, failed
  teacher collection, or failed T022 report generation must fail closed.
- Writers emit only the current scale-up manifest schema. Readers for existing
  input artifacts must use their current migration paths before business logic
  runs.
- CLI parsing remains thin. Workflows live in `src/sts_combat_rl/commands/`;
  reusable source planning, manifest, stability, and formatting logic lives
  below that layer.
- Do not add Gymnasium, Stable-Baselines3, game files, jars, mods, save files,
  large binaries, or new mandatory dependencies. PyTorch remains optional under
  the existing `train` dependency group and should not be needed by this
  command.

## Deliverables

- A reusable source-selection and scale-up manifest builder below the command
  layer.
- A command workflow under `src/sts_combat_rl/commands/`.
- CLI parser, validation, and routing for the scale-up command and options.
- A current machine-readable scale-up manifest schema with schema id/version,
  source identities, source-selection plan, budget list, generated artifact
  identities, generated T022 report identities, search configuration,
  information-regime summary, coverage summary, cross-budget stability summary,
  and problems.
- Deterministic human-readable stderr formatting.
- Focused unit tests for source planning, deterministic source limiting,
  source-pool and T021 identity linkage, budget validation, manifest
  determinism, cross-budget action agreement, malformed artifact failure, and
  CLI validation.
- A WSL smoke-scale PR evidence run that writes generated artifacts outside the
  repository or under ignored artifact paths.

## Acceptance Criteria

- The scale-up command loads current and migrated A20 source-pool fixtures.
- Given the same source pool, seed, source limit, budgets, and native source,
  the source-selection plan and non-timing manifest content are deterministic.
- The same selected source identities are used for every requested budget.
- Source selection is reported by rule-defined structural metadata and does
  not use deck, relic, route-quality, or winnability filters.
- Every generated teacher artifact has a corresponding T022 report linked to
  the same source pool and optional T021 report.
- Unique natural source coverage does not increase when multiple budgets,
  teacher rows, or root rows are generated from the same source checkpoint.
- Teacher action agreement across budgets is summarized by source checkpoint
  and structural metadata. Low agreement is reported as label instability, not
  hidden or treated as policy failure.
- Soft root-visit targets remain separate from teacher action labels and are
  summarized separately from action agreement.
- A valid but under-covered A20 scale-up smoke run exits successfully while
  reporting the exact coverage gaps and broad-training limitations.
- The command exits nonzero for invalid source artifacts, unsupported schemas,
  malformed source identities, missing or mixed information-regime provenance,
  T021 source identity mismatches, teacher collection failures, or T022 report
  failures.
- The implementation does not train a model, run model-guided search, add
  native simulator code, change controller behavior, or add prohibited
  dependencies.
- Existing T006, T021, and T022 artifact readers and writers remain backward
  compatible.

## Required Verification

Run the standard local gates:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Run focused tests added or touched by the task, including source planning,
budget validation, source-pool linkage, optional T021 linkage, T022 report
generation, cross-budget stability, manifest determinism, schema failures, and
CLI tests.

Run the source verifier before WSL evidence:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run a smoke-scale WSL scale-up chain. Exact output paths may differ, but the PR
must include exact commands and summaries:

```powershell
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; rm -rf /tmp/stsrl-t023; mkdir -p /tmp/stsrl-t023; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/stsrl-t023/a20-pool.jsonl --sim-seed 1 --sim-episodes 10 --sim-ascension 20 --sim-steps 300 --battle-start-sample-count 32 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-battle-start-coverage /tmp/stsrl-t023/a20-pool.jsonl --a20-coverage-output /tmp/stsrl-t023/coverage.json --battle-start-restore-limit 0 --battle-start-sample-count 32 --pytorch-gate-required-ascensions 20 --pytorch-gate-required-acts 1 2 3 4 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-oracle-teacher-scaleup /tmp/stsrl-t023/a20-pool.jsonl --oracle-teacher-scaleup-output-dir /tmp/stsrl-t023/teacher-scaleup --oracle-teacher-scaleup-budgets 20 50 100 --oracle-teacher-scaleup-source-limit 32 --oracle-teacher-scaleup-seed 1 --oracle-teacher-scaleup-coverage-report /tmp/stsrl-t023/coverage.json --log-file -"
```

The final command should exit zero for a valid under-covered smoke-scale source
pool while clearly reporting:

- selected unique source count and structural coverage;
- generated teacher row counts per budget;
- root row, root visit, native simulator step, and search simulation counts
  per budget;
- cross-budget teacher-action agreement;
- soft-target summary or explicit unavailability;
- generated T022 report identities;
- that the data is `full_simulator_state_oracle_like` and not
  normal-information, live-game, broad-training, or controller-strength
  evidence.

## Legacy Reference

Consult current merged code and tests for T006, T009, T016, T018, T021, and
T022. The legacy integration branch may be inspected only for report or
workflow ideas, not wholesale porting.

## PR Report

The pull request must include:

- task ID and link to this document;
- scale-up manifest schema id/version;
- CLI interface summary;
- exact local and WSL verification commands and results;
- source manifest identity and pinned `sts_lightspeed` commit used for WSL
  evidence;
- source pool identity, optional T021 report identity, selected source count,
  source-selection seed, source limit, and selected structural coverage;
- requested budget tiers and root-selection rule;
- per-budget teacher artifact identities, T022 report identities, teacher row
  counts, root row counts, root visit counts, native simulator step counts, and
  search simulation counts;
- cross-budget teacher-action agreement and soft-target stability summary;
- explicit statement that the teacher data is
  `full_simulator_state_oracle_like` and is not normal-information or live-game
  evidence;
- explicit statement that smoke-scale under-covered results are not broad
  training evidence and not controller-strength evidence;
- compatibility notes for existing T006/T021/T022 artifact readers/writers;
- legacy files consulted, if any;
- known limitations and follow-up recommendations for model-guided search,
  fixed A20 benchmark reporting, broader A20 data collection, and
  normal-information search groundwork.
