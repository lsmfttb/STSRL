# T022: A20 Oracle Teacher Dataset Report

Status: `READY`.

## Objective

Add a versioned report for A20 Oracle-like teacher datasets that ties a teacher
JSONL artifact back to its natural battle-start source coverage, search budget,
root statistics, public-context/resource availability, and T021 broad-training
coverage gaps.

The result must answer a narrow question: what Oracle-like A20 teacher data was
collected, from which natural source starts and structural strata, with what
native search budget and root-target quality, and what gaps remain before the
data is useful for broad model/search work.

This task is reporting and scale-up readiness only. It must not train a model,
promote a controller, or describe Oracle-like hidden-state search as
normal-information performance.

## Current Main Baseline

Current `main` already has:

- portable natural battle-start pools from T004;
- fixed structural cohorts from T005;
- explicitly `full_simulator_state_oracle_like` teacher collection from T006;
- optional PyTorch plumbing and fail-closed broad-training gates from T009;
- structured resource outcomes and public-context artifact propagation from
  T012/T016/T018;
- stable pinned `sts_lightspeed` source integration from T017/T020;
- current-schema A20 coverage reporting from T021.

The current gap is that Oracle teacher collection emits a collection summary
while writing the teacher JSONL artifact, but there is no reusable
current-schema report that can later audit a saved teacher dataset against its
source pool and T021 coverage report. A PR report can describe teacher rows and
root statistics manually, but downstream model/search tasks need a deterministic
machine-readable teacher dataset report before scaling teacher artifacts or
comparing guided search.

## Dependencies

- T004, T005, T006, T009, T012, T016, T017, T018, T020, and T021 are complete.
- T007 is cancelled and is not a dependency.

## Scope

- Add a focused report builder under the simulator layer for Oracle teacher
  datasets.
- Add a CLI entry point:

  ```text
  --oracle-teacher-dataset-report TEACHER_JSONL
  ```

  The command loads one current or migrated Oracle teacher JSONL artifact,
  optionally loads the source natural battle-start pool and T021 coverage
  report, optionally writes a machine-readable report, and prints a
  deterministic human-readable report to stderr.

- Add optional CLI flags:

  ```text
  --oracle-teacher-source-pool POOL_PATH
  --oracle-teacher-coverage-report COVERAGE_JSON
  --oracle-teacher-report-output PATH
  ```

- Define a current machine-readable report schema, for example
  `oracle-teacher-dataset-report-v1`.
- Report teacher coverage by rule-defined structural metadata:

  ```text
  ascension
  act
  room_type
  encounter_id
  source_run_id
  source_checkpoint_id
  ```

- Report teacher artifact identity, source-pool identity, optional T021 report
  identity, pinned source manifest identity, command configuration, and schema
  versions.
- Report total teacher rows, unique source starts, root rows, root visits,
  native simulator steps, search simulations, root-selection rule, teacher
  action availability, soft visit target availability, and deterministic row
  digest.
- Preserve the distinction between teacher action and soft root-visit targets.
- Preserve and report the `full_simulator_state_oracle_like` information
  regime. Any missing, mixed, or non-Oracle information-regime provenance must
  be an explicit problem.
- When a source pool is provided, verify that every teacher source checkpoint
  exists in that pool and that embedded source metadata agrees with the pool
  record where current schemas provide the fields.
- When a T021 coverage report is provided, verify that its natural-pool
  identity matches the supplied source pool and report the T021 broad-training
  gate status alongside teacher coverage. Under-coverage is not a command
  failure.
- Keep natural source coverage separate from repeated teacher decisions or root
  rows. Root rows and visits are search statistics, not new source coverage.
- Add deterministic formatting for both machine-readable JSON and stderr
  summary.
- Add tests with small fixtures covering valid teacher-only reports,
  teacher-plus-source-pool reports, optional T021 coverage linkage, repeated
  source starts, missing metadata, mixed information regime, source mismatch,
  malformed artifacts, and deterministic JSON output.

## Out Of Scope

- Broad PyTorch training or checkpoint promotion.
- Model-guided search controller implementation.
- Fixed A20 benchmark comparison between controllers.
- Normal-information belief search or hidden-future sampling.
- New `sts_lightspeed` native APIs or native game-code changes.
- Constructed supplement teacher collection unless a future task adds a
  restorable constructed-source teacher boundary.
- Treating root rows, repeated teacher decisions, or constructed variants as
  new natural source coverage.
- Claiming A20 policy strength, live-game readiness, or normal-information
  search performance.
- Checking large generated teacher datasets, pools, or reports into the
  repository.

## Design Constraints

- The actual game is the final mechanics authority. `sts_lightspeed` remains
  the current large-scale simulator substrate and authoritative simulator for
  this workflow; do not reimplement game mechanics in Python.
- Any native search teacher data in this task is
  `full_simulator_state_oracle_like` and must never be silently reported as
  normal-information evidence.
- Artifact or schema validation failures, malformed source identities, mixed
  information regimes, missing required teacher provenance, or source-pool
  mismatches must fail closed.
- Under-covered A20 strata are expected and should be reported, not hidden. They
  are not command failures by themselves.
- Public-context and structured-outcome missingness from the source pool or
  T021 report must remain explicit.
- CLI parsing remains thin. Put the workflow in `src/sts_combat_rl/commands/`
  and reusable report logic below that layer.
- Writers emit only the current report schema. Readers for existing input
  artifacts must use their current migration paths before business logic runs.

## Deliverables

- A reusable Oracle teacher dataset report builder under the simulator layer.
- A command workflow under `src/sts_combat_rl/commands/`.
- CLI parser and routing for:

  ```text
  --oracle-teacher-dataset-report
  --oracle-teacher-source-pool
  --oracle-teacher-coverage-report
  --oracle-teacher-report-output
  ```

- A current machine-readable report schema with schema id, version, input
  artifact identities, source manifest identity, command configuration, teacher
  dataset coverage, source-pool linkage, optional T021 coverage linkage, search
  statistics, information-regime summary, and problems.
- A deterministic human-readable formatter for PR evidence.
- Focused unit tests and CLI tests.
- Documentation impact notes in the PR. Project-level status documents are
  updated by the main maintainer after merge, not rewritten opportunistically
  unless this task document is changed to require it.

## Acceptance Criteria

- The new command loads current and migrated Oracle teacher fixtures and emits a
  deterministic report.
- The report includes all required teacher, source, search-statistic,
  information-regime, public-context/outcome, optional T021, and problem
  sections.
- Unique natural source counts do not increase when multiple teacher rows or
  root rows come from the same source checkpoint.
- Missing structural metadata is visible in the report and contributes to
  explicit problems instead of being guessed.
- Mixed or missing information-regime provenance is visible and causes the
  command to exit nonzero.
- A valid but under-covered A20 teacher dataset exits successfully while
  reporting the exact coverage gaps.
- The command exits nonzero for invalid teacher artifacts, malformed source
  identities, source-pool mismatches, T021 source identity mismatches, or
  unsupported schemas.
- The implementation does not train a model, run model-guided search, add native
  simulator code, or change controller behavior.
- Existing T006/T021 artifact readers and writers remain backward compatible.

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

Run focused tests added or touched by the task, including teacher-report,
teacher artifact, source-pool linkage, T021 coverage linkage, schema failure,
and CLI tests.

Run the source verifier before WSL evidence:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run a smoke-scale WSL teacher-report chain. Exact output paths may differ, but
the PR must include exact commands and summaries:

```powershell
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; mkdir -p /tmp/stsrl-t022; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/stsrl-t022/a20-pool.jsonl --sim-seed 1 --sim-episodes 10 --sim-ascension 20 --sim-steps 300 --battle-start-sample-count 32 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-battle-start-coverage /tmp/stsrl-t022/a20-pool.jsonl --a20-coverage-output /tmp/stsrl-t022/coverage.json --battle-start-restore-limit 0 --battle-start-sample-count 32 --pytorch-gate-required-ascensions 20 --pytorch-gate-required-acts 1 2 3 4 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-oracle-search-teacher /tmp/stsrl-t022/a20-pool.jsonl --oracle-teacher-output /tmp/stsrl-t022/teacher.jsonl --oracle-search-simulations 20 --sim-ascension 20 --sim-steps 300 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --oracle-teacher-dataset-report /tmp/stsrl-t022/teacher.jsonl --oracle-teacher-source-pool /tmp/stsrl-t022/a20-pool.jsonl --oracle-teacher-coverage-report /tmp/stsrl-t022/coverage.json --oracle-teacher-report-output /tmp/stsrl-t022/teacher-report.json --log-file -"
```

The final command should exit zero for a valid under-covered teacher dataset
while clearly reporting that the data is Oracle-like and not broad-training,
normal-information, live-game, or controller-strength evidence.

## Legacy Reference

Consult current merged code and tests for T006, T009, T016, T018, and T021.
The legacy integration branch may be inspected only for report ideas, not
wholesale porting.

## PR Report

The pull request must include:

- task ID and link to this document;
- report schema id/version;
- CLI interface summary;
- exact local and WSL verification commands and results;
- source manifest identity and pinned `sts_lightspeed` commit used for WSL
  evidence;
- teacher artifact row count, unique natural source count, root row count,
  root visit count, native simulator step count, search simulations, and root
  selection rule;
- per-ascension/per-act and per-room/encounter teacher coverage summary;
- source-pool and optional T021 coverage-linkage summary;
- explicit statement that the teacher data is `full_simulator_state_oracle_like`
  and is not normal-information or live-game evidence;
- explicit statement that under-covered smoke-scale results are not broad
  training evidence;
- compatibility notes for existing artifact readers/writers;
- legacy files consulted, if any;
- known limitations and follow-up recommendations for model-guided search,
  fixed A20 benchmark reporting, and normal-information search groundwork.
