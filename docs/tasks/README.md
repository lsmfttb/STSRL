# Task Index

Tasks are the executable specification for feature branches and pull requests.
Read [`../collaboration_workflow.md`](../collaboration_workflow.md) before
starting work.

## Active Backlog

| ID | Status | Task | Depends On | Legacy Reference Areas |
|---|---|---|---|---|
| T001 | DONE | [Main quality baseline](T001-main-quality-baseline.md) | none | formatting and lint cleanup |
| T002 | DONE | [Controlled-run foundation](T002-controlled-run-foundation.md) | T001 | controller contracts, controlled run, rollout executor |
| T003 | READY | [Artifact provenance foundation](T003-artifact-provenance-foundation.md) | T002 | artifact versioning, decision records |
| T004 | BLOCKED | [Battle-start checkpoint pool](T004-battle-start-checkpoint-pool.md) | T002, T003, T010 | checkpoint restore, battle-start pool |
| T005 | BLOCKED | [Fixed structural battle evaluation](T005-fixed-battle-evaluation.md) | T004 | fixed evaluation set and runner |
| T006 | BLOCKED | [Oracle search teacher pipeline](T006-oracle-search-teacher.md) | T003, T004, T005 | search policy, teacher, search dataset |
| T007 | BLOCKED | [Complete public run history](T007-complete-public-run-history.md) | T002, T003, T004 | public context/history and native projections |
| T008 | BLOCKED | [A20 constructed battle supplements](T008-a20-constructed-supplements.md) | T003, T004 | battle-start transforms and approximate HP policy |
| T009 | BLOCKED | [PyTorch search-guidance model](T009-pytorch-search-guidance.md) | T003, T006, T007, T011, T012 | optional train dependency and policy/value model |
| T010 | READY | [Stochastic non-combat driver](T010-stochastic-non-combat-driver.md) | T002 | non-combat policy and native visible action/resource support |
| T011 | BLOCKED | [Tactical feature contract v2](T011-tactical-feature-contract-v2.md) | T003 | feature, trainer-input, and model-input upgrades |
| T012 | BLOCKED | [Structured battle resource outcomes](T012-structured-resource-outcomes.md) | T003, T004, T010 | persistent resource snapshots and outcome vectors |

Only `READY` tasks should receive a new branch. After a prerequisite merges,
the main maintainer reviews dependent specifications against the new `main`
before changing their state.

`BLOCKED` task specifications define intended boundaries but may be refined by
the main maintainer before becoming `READY`. Once a task is `READY`, its
published acceptance criteria are the review contract; scope changes require a
document update before acceptance.

## Standard Local Gates

Unless a task explicitly says otherwise, every task must pass:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Task-specific WSL and artifact gates are additional requirements.

## Legacy Mapping

Commit `d56e10e` is intentionally not mergeable as one unit. Its major areas
are mapped as follows:

- controller and execution modules: T002;
- artifact migrations, decision provenance, and schema readers: T003;
- checkpoint patches, restore verification, and battle-start pools: T004;
- deterministic structural cohorts and restored-battle evaluation: T005;
- native search interfaces and search-training collection: T006;
- public context and full public-history work: T007;
- battle-start transforms and practical A20 supplements: T008;
- PyTorch policy/value model and training gates: T009;
- stochastic non-combat behavior and native potion/resource visibility: T010;
- tactical feature, trainer-input, and model-input expansion: T011;
- structured persistent resource outcomes: T012.

CLI decomposition and command modules are not a standalone task. Each task may
move only its own workflows out of `cli.py`, following the architecture
contract. A later dedicated CLI cleanup task should be published only if
duplication remains after these tasks.

Pure-Python linear scorer, policy-gradient, and policy-comparison experiments
from the legacy commit are explicitly unscheduled. They are preserved by the
legacy reference and may be published later only if they answer a concrete
research question.

New task documents should start from [`TEMPLATE.md`](TEMPLATE.md).
