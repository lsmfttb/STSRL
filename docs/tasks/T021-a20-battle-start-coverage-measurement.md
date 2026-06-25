# T021: A20 Battle-Start Coverage Measurement

Status: `READY`.

## Objective

Add a versioned A20 battle-start coverage report that measures how far the
current natural, sampled, and constructed battle-start data is from broad
training readiness and from the data coverage needed by later fixed A20
benchmark work.

The result must answer a narrow question: what A20 battle-start coverage exists
today, what is missing by structural metadata, and which exact gaps keep the
T009 broad-training gate closed. It must not train a model or claim controller
strength.

## Current Main Baseline

Current `main` already has:

- portable natural battle-start pools from T004;
- fixed structural cohort selection and restored-battle evaluation from T005;
- conservative constructed A20 battle-start supplements from T008;
- a fail-closed T009 broad-training scale/distribution gate;
- public-context artifact propagation from T016;
- structured battle resource outcomes and native terminal identity coverage
  from T012/T018;
- the active `sts_lightspeed` fork integration branch from T020.

The current evidence remains smoke-scale. `current_status.md` explicitly says
that broad neural training, model-guided native search, and fixed-evaluation
performance improvement are not implemented. Existing reports describe parts
of coverage, but there is no single current-schema report that combines:

- natural source coverage;
- sampled optimization-weight draws;
- constructed supplement counts;
- restore verification;
- structured outcome availability;
- public-context availability;
- per-ascension/per-act broad-training gate gaps.

## Dependencies

- T004, T005, T008, T009, T010, T012, T016, T017, T018, and T020 are complete.
- T007 is cancelled and is not a dependency.

## Scope

- Add a focused report builder for A20 battle-start coverage.
- Add a CLI entry point:

  ```text
  --lightspeed-a20-battle-start-coverage POOL_PATH
  ```

  The command loads one current or migrated portable natural battle-start pool,
  optionally loads one constructed supplement artifact, optionally writes a
  machine-readable report, prints a human-readable report to stderr, and uses
  the existing fresh-adapter restore verifier.

- Add optional CLI flags:

  ```text
  --a20-coverage-constructed-artifact PATH
  --a20-coverage-output PATH
  ```

  Reuse the existing `--battle-start-restore-limit` and
  `--pytorch-gate-*` options for restore scope and broad-training gate
  thresholds.

- Define a current machine-readable report schema, for example
  `a20-battle-start-coverage-report-v1`.
- Report natural battle-start coverage separately from sampled training weight
  and constructed supplements.
- Count unique stable source identities from natural source checkpoints or
  source run/battle identity. Repeated samples and constructed variants must
  not increase unique natural coverage.
- Report coverage by rule-defined structural metadata:

  ```text
  ascension
  act
  room_type
  encounter_id
  distribution_kind
  ```

- Report fixed broad-training gate cells using the configured T009 gate:
  records, unique sources, public-context statuses, structured-outcome
  statuses, pass/fail, and explicit problems for every required
  ascension/act cell.
- Report restore verification counts and failures for the loaded natural pool.
- Report constructed supplement counts separately:
  audit rows, accepted constructed rows, no-op rows, unsupported rows,
  transform kinds, and source distribution identity.
- Report natural pool problems, missing metadata counts, source-run terminal
  and truncation counts, completed battle outcome availability, and structured
  resource outcome availability.
- Add deterministic formatting for both the machine-readable artifact and the
  stderr summary.
- Add tests with small fixtures that cover natural-only, natural-plus-
  constructed, missing metadata, repeated samples, under-covered gate cells,
  restore failures, and mismatched constructed-source provenance.

## Out Of Scope

- Broad PyTorch training or checkpoint promotion.
- Any model-guided search controller.
- Oracle teacher dataset scale-up.
- Fixed battle benchmark comparison between controllers.
- Non-combat driver behavior changes.
- New `sts_lightspeed` native APIs or native game-code changes.
- Gymnasium, Stable-Baselines3, PPO, or a local game-mechanics environment.
- Treating constructed supplements as natural coverage.
- Filtering or weighting states by hand-written deck, relic, or route quality.
- Claiming A20 policy strength, live-game readiness, or normal-information
  search performance.
- Deleting or archiving historical `sts_lightspeed` fork branches; that remains
  tracked by `lsmfttb/sts_lightspeed#7`.

## Design Constraints

- `sts_lightspeed` remains the authoritative game implementation. Restore
  checks must use the pinned source manifest through WSL for real simulator
  evidence.
- Under-coverage is expected and should be reported, not hidden. It is not a
  command failure by itself.
- Artifact or schema validation failures, restore failures, source-provenance
  mismatches, malformed records, or missing required provenance must fail
  closed.
- The report must keep natural-run, sampled training-weight, and constructed
  supplement distributions separate.
- A0 data may appear only if explicitly tagged; it must not satisfy A20 gate
  requirements.
- Public-context and structured-outcome missingness must remain explicit.
- The report may use Oracle-like or native checkpoint restore mechanics only
  for verification. It must not expose hidden simulator state to normal
  controller, feature, or training records.
- CLI parsing remains thin. Put the workflow in `src/sts_combat_rl/commands/`
  and reusable logic below that layer.
- Writers emit only the current report schema. Readers for existing input
  artifacts must use their current migration paths before business logic runs.
- Do not check large generated pools, constructed artifacts, or coverage
  reports into the repository. Small regression fixtures are allowed.

## Deliverables

- A reusable report builder under the simulator layer.
- A command workflow under `src/sts_combat_rl/commands/`.
- CLI parser and routing for:

  ```text
  --lightspeed-a20-battle-start-coverage
  --a20-coverage-constructed-artifact
  --a20-coverage-output
  ```

- A current machine-readable coverage report schema with schema id, version,
  input artifact identities, source manifest identity, command configuration,
  natural coverage, constructed coverage, restore verification, training-gate
  cells, and problems.
- A deterministic human-readable formatter for PR evidence.
- Focused unit tests and CLI tests.
- Documentation impact notes in the PR. Project-level status documents are
  updated by the main maintainer after merge, not rewritten opportunistically
  unless this task document is changed to require it.

## Acceptance Criteria

- The new command loads current and migrated natural battle-start pool fixtures
  and emits a deterministic report.
- The report includes all required natural, constructed, restore,
  public-context, structured-outcome, and broad-training-gate sections.
- Natural unique-source counts do not increase when the same source checkpoint
  is sampled repeatedly or used to produce constructed supplements.
- Constructed supplements are counted as constructed rows and as training rows,
  but not as new natural source coverage.
- Missing structural metadata is visible in the report and contributes to the
  relevant gate problems instead of being guessed.
- The T009 gate defaults still fail closed for the current smoke-scale A20
  data, and the report states why per ascension/act cell.
- The command exits successfully for a valid but under-covered dataset.
- The command exits nonzero for invalid artifacts, restore failures within the
  requested restore scope, malformed source identities, or mismatched
  constructed-source provenance.
- The implementation does not train a model, run teacher search, add native
  simulator code, or change controller behavior.
- Existing T004/T005/T008/T009/T012/T016/T018 behavior and artifact schemas
  remain backward compatible.

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

Run focused tests added or touched by the task, including coverage-report,
CLI, natural-pool, constructed-supplement, restore, and T009 gate tests.

Run the source verifier before WSL coverage evidence:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run a smoke-scale WSL coverage chain. The exact output paths may differ, but
the PR must include the exact commands and summaries:

```powershell
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; mkdir -p /tmp/stsrl-t021; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/stsrl-t021/a20-pool.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --battle-start-sample-count 16 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-constructed-battle-start-audit --constructed-start-pool /tmp/stsrl-t021/a20-pool.jsonl --constructed-start-output /tmp/stsrl-t021/constructed.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-battle-start-coverage /tmp/stsrl-t021/a20-pool.jsonl --a20-coverage-constructed-artifact /tmp/stsrl-t021/constructed.jsonl --a20-coverage-output /tmp/stsrl-t021/coverage.json --battle-start-restore-limit 0 --pytorch-gate-required-ascensions 20 --pytorch-gate-required-acts 1 2 3 4 --log-file -"
```

The final command should exit zero for a valid smoke-scale dataset while
reporting that broad training is not ready unless the dataset genuinely meets
the configured gate.

## Legacy Reference

Consult current merged code and tests for T004, T005, T008, T009, T012, T016,
and T018. The legacy integration branch may be inspected only for report ideas,
not wholesale porting.

## PR Report

The pull request must include:

- task ID and link to this document;
- report schema id/version;
- CLI interface summary;
- exact local and WSL verification commands and results;
- source manifest identity and pinned `sts_lightspeed` commit used for WSL
  evidence;
- natural pool source run count, natural battle-start count, unique source
  count, completed battle/outcome availability, and restore result summary;
- constructed artifact source count, constructed row count, no-op/unsupported
  counts, and transform-kind counts;
- broad-training gate configuration and per-cell pass/fail summary;
- explicit statement that under-covered smoke-scale results are not broad
  training evidence;
- compatibility notes for existing artifact readers/writers;
- legacy files consulted, if any;
- known limitations and follow-up recommendations for T022/T023/T024.
