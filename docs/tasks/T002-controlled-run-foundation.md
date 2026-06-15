# T002: Controlled-Run Foundation

Status: `IN_REVIEW` in PR #2.

Current review blockers:

- scorer and custom-chooser behavior is not completely represented in
  provenance;
- effective action-space configuration is not persisted in run provenance;
- rollout helpers still construct hidden default controllers;
- provenance configuration is not deeply immutable;
- the pull-request report required below is incomplete.

## Objective

Replace the current parallel rollout paths with explicit online controllers,
complete controller provenance, and one authoritative complete-run advancement
function. This is the foundation for trustworthy datasets, search, and
evaluation.

## Current Baseline

`main` has separate helpers for simulator rollout, policy rollout, and
battle-agent rollout. Policies expose action selection, but there is no single
controller contract carrying behavior provenance and no authoritative executor
shared by complete-run workflows.

## Scope

- Define a framework-neutral online-controller contract.
- Define immutable, serializable controller provenance containing every
  behavior-changing setting available at this stage.
- Provide explicit adapters for existing decision policies.
- Provide an explicit routed controller that separates battle policy from the
  non-combat driver.
- Introduce one authoritative complete-run executor that owns:
  - snapshot-to-decision-context construction;
  - action-space filtering;
  - controller invocation;
  - selected-index validation;
  - simulator stepping;
  - observer callbacks and bounded termination.
- Refactor existing complete-run smoke and battle-agent workflows to use that
  executor without changing their public behavior.
- Preserve the seeded stochastic non-combat option. No dataset helper may
  silently construct a default controller.
- Move only task-owned CLI workflow code into `src/sts_combat_rl/commands/` if
  needed; CLI argument parsing and routing remain in `cli.py`.

## Out Of Scope

- Checkpoints, replay restore, battle-start pools, search, PyTorch, artifact
  migrations, public run history, or constructed states.
- New non-combat strategy design.
- Changing feature vectors, reward definitions, or policy strength.

## Design Constraints

- Existing policy names remain behavior contracts.
- Battle and non-combat controller provenance remain separately inspectable.
- Complete-run advancement has one authoritative implementation.
- Specialized future replay or restored-battle loops may differ only at their
  explicit boundary and must reuse selection validation semantics.
- stdout remains reserved for protocol commands.

## Deliverables

- Controller contract and provenance types.
- Routed battle/non-combat controller implementation.
- Authoritative controlled-run executor.
- Existing workflows migrated to the executor.
- Focused unit tests for routing, provenance, selection validation, deterministic
  seeded behavior, observer calls, and termination.
- Regression tests for existing CLI smokes.

## Acceptance Criteria

- No complete-run workflow duplicates the full select/validate/step loop.
- Every action in controlled runs can be attributed to explicit controller
  provenance.
- Existing public CLI behavior and fixture smokes remain compatible.
- No new hidden default battle or non-combat controller is introduced.
- Required checks and WSL smoke pass.

## Required Verification

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Real simulator:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-sweep --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

## Legacy Reference

The following files in commit `d56e10e` may be consulted, but must not be
wholesale cherry-picked:

```text
src/sts_combat_rl/sim/controller_contract.py
src/sts_combat_rl/sim/decision_context.py
src/sts_combat_rl/sim/online_controller.py
src/sts_combat_rl/sim/controlled_run.py
src/sts_combat_rl/sim/rollout_executor.py
tests/test_online_controller.py
```

## PR Report

Include:

- a diagram or concise description of the final execution path;
- list of old loops removed or retained and why;
- provenance example for a routed run;
- exact local and WSL verification results;
- any compatibility or follow-up concern.
