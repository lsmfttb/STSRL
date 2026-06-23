# Task Index

Tasks are the executable specification for feature branches and pull requests.
Read [`../collaboration_workflow.md`](../collaboration_workflow.md) before
starting work.

## Active Backlog

| ID | Status | Task | Depends On | Legacy Reference Areas |
|---|---|---|---|---|
| T001 | DONE | [Main quality baseline](T001-main-quality-baseline.md) | none | formatting and lint cleanup |
| T002 | DONE | [Controlled-run foundation](T002-controlled-run-foundation.md) | T001 | controller contracts, controlled run, rollout executor |
| T003 | DONE | [Artifact provenance foundation](T003-artifact-provenance-foundation.md) | T002 | artifact versioning, decision records |
| T004 | DONE | [Battle-start checkpoint pool](T004-battle-start-checkpoint-pool.md) | T002, T003, T010 | checkpoint restore, battle-start pool |
| T005 | DONE | [Fixed structural battle evaluation](T005-fixed-battle-evaluation.md) | T004 | fixed evaluation set and runner |
| T006 | DONE | [Oracle search teacher pipeline](T006-oracle-search-teacher.md) | T003, T004, T005, T017 | search policy, teacher, search dataset |
| T007 | CANCELLED | [Complete public run history (superseded)](T007-complete-public-run-history.md) | — | replaced by T014--T016 |
| T008 | READY | [A20 constructed battle supplements](T008-a20-constructed-supplements.md) | T003, T004, T016, T017 | battle-start transforms and approximate HP policy |
| T009 | BLOCKED | [PyTorch search-guidance model](T009-pytorch-search-guidance.md) | T003, T006, T011, T012, T016, T018 | optional train dependency and policy/value model |
| T010 | DONE | [Stochastic non-combat driver](T010-stochastic-non-combat-driver.md) | T002 | non-combat policy and native visible action/resource support |
| T011 | DONE | [Tactical feature contract v2](T011-tactical-feature-contract-v2.md) | T003 | feature, trainer-input, and model-input upgrades |
| T012 | DONE | [Structured battle resource outcomes](T012-structured-resource-outcomes.md) | T003, T004, T010, T016, T017 | persistent resource snapshots and outcome vectors |
| T013 | DONE | [Live CommunicationMod runtime adapter](T013-live-communicationmod-runtime-adapter.md) | T003, T011 | trained/search controller deployment in the real game |
| T014 | DONE | [Native public projection capability](T014-native-public-projection-capability.md) | T002, T003, T004, T010, T011 | native public projection and action parity |
| T015 | DONE | [Public run context and controlled history](T015-public-run-context-and-controlled-history.md) | T002, T003, T004, T011, T014 | sanitized context and ordered history |
| T016 | DONE | [Public-context artifacts, replay, and audit](T016-public-context-artifacts-replay-and-audit.md) | T003, T004, T005, T011, T014, T015 | migrations, replay, and coverage audit |
| T017 | DONE | [Stable sts_lightspeed source integration](T017-stable-lightspeed-source-integration.md) | T004, T010, T014, T016 | external source manifest and verifier |
| T018 | READY | [Native terminal resource identity surface](T018-native-terminal-resource-identity.md) | T012, T017 | native terminal potion/deck/relic/key identities |

Only `READY` tasks should receive a new branch. After a prerequisite merges,
the main maintainer reviews dependent specifications against the new `main`
before changing their state.

`BLOCKED` task specifications define intended boundaries but may be refined by
the main maintainer before becoming `READY`. Once a task is `READY`, its
published acceptance criteria are the review contract; scope changes require a
document update before acceptance.

## Published Queue

- T005 is complete. It establishes the fixed-evaluation boundary without
  changing public-context schemas.
- T017 is complete. It replaces the day-to-day local `sts_lightspeed`
  patch-stack workflow with a pinned external source integration for future
  native-surface tasks.
- T006 is complete. It adds an explicitly Oracle-like teacher/evaluation path
  on immutable T005 cohorts and cannot be reported as normal-information or
  real-game performance.
- T007 is `CANCELLED`. Its replacement sequence completed T014 for native
  capability, T015 for sanitized in-memory context/history, and T016 for
  artifact propagation/replay/audit. See the
  [T007 review handoff](../t007_review_handoff_2026-06-22.md).
- T012 is complete. It establishes the structured outcome schema, artifact
  propagation, migration, reporting, and explicit native missingness boundary.
- T008 and T018 are `READY`. T018 owns full native identity-bearing terminal
  resource coverage. T009 remains blocked by T018 and its remaining named data
  prerequisites.

## Standard Local Gates

Unless a task explicitly says otherwise, every task must pass. Run these after
an editable install or with `PYTHONPATH=src` in an uninstalled checkout:

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
- native public projection, public context/history, and propagation/audit:
  T014, T015, and T016;
- external simulator source integration and patch-stack retirement: T017;
- battle-start transforms and practical A20 supplements: T008;
- PyTorch policy/value model and training gates: T009;
- stochastic non-combat behavior and native potion/resource visibility: T010;
- tactical feature, trainer-input, and model-input expansion: T011;
- structured persistent resource outcomes and explicit missingness: T012;
- native terminal resource identity coverage: T018.

T013 supplies the shared CommunicationMod adapter and captured-sample
compatibility gate. Simulator-only training experiments do not depend on it.
A trained or search controller still needs to use that adapter and earn its own
captured-sample or interactive evaluation evidence before it is described as
live-game validated.

CLI decomposition and command modules are not a standalone task. Each task may
move only its own workflows out of `cli.py`, following the architecture
contract. A later dedicated CLI cleanup task should be published only if
duplication remains after these tasks.

Pure-Python linear scorer, policy-gradient, and policy-comparison experiments
from the legacy commit are explicitly unscheduled. They are preserved by the
legacy reference and may be published later only if they answer a concrete
research question.

New task documents should start from [`TEMPLATE.md`](TEMPLATE.md).
