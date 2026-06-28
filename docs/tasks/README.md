# Task Index

Tasks are the executable specification for feature branches and pull requests.
Read [`../collaboration_workflow.md`](../collaboration_workflow.md) before
starting work.

The Active Backlog table below is the only authoritative source for task
lifecycle state. Individual task documents intentionally omit mutable
`Status:` lines; they define scope, acceptance criteria, and historical
disposition where needed. `current_status.md` and roadmap files may summarize
the current milestone, but they do not override this table.

## Active Backlog

| ID | Status | Task | Depends On | Legacy Reference Areas |
|---|---|---|---|---|
| T001 | DONE | [Main quality baseline](T001-main-quality-baseline.md) | none | formatting and lint cleanup |
| T002 | DONE | [Controlled-run foundation](T002-controlled-run-foundation.md) | T001 | controller contracts, controlled run, rollout executor |
| T003 | DONE | [Artifact provenance foundation](T003-artifact-provenance-foundation.md) | T002 | artifact versioning, decision records |
| T004 | DONE | [Battle-start checkpoint pool](T004-battle-start-checkpoint-pool.md) | T002, T003, T010 | checkpoint restore, battle-start pool |
| T005 | DONE | [Fixed structural battle evaluation](T005-fixed-battle-evaluation.md) | T004 | fixed evaluation set and runner |
| T006 | DONE | [Oracle search teacher pipeline](T006-oracle-search-teacher.md) | T003, T004, T005, T017 | search policy, teacher, search dataset |
| T007 | CANCELLED | [Complete public run history (superseded)](T007-complete-public-run-history.md) | none | replaced by T014--T016 |
| T008 | DONE | [A20 constructed battle supplements](T008-a20-constructed-supplements.md) | T003, T004, T016, T017 | battle-start transforms and approximate HP policy |
| T009 | DONE | [PyTorch search-guidance model](T009-pytorch-search-guidance.md) | T003, T006, T011, T012, T016, T018 | optional train dependency and policy/value model |
| T010 | DONE | [Stochastic non-combat driver](T010-stochastic-non-combat-driver.md) | T002 | non-combat policy and native visible action/resource support |
| T011 | DONE | [Tactical feature contract v2](T011-tactical-feature-contract-v2.md) | T003 | feature, trainer-input, and model-input upgrades |
| T012 | DONE | [Structured battle resource outcomes](T012-structured-resource-outcomes.md) | T003, T004, T010, T016, T017 | persistent resource snapshots and outcome vectors |
| T013 | DONE | [Live CommunicationMod runtime adapter](T013-live-communicationmod-runtime-adapter.md) | T003, T011 | trained/search controller deployment in the real game |
| T014 | DONE | [Native public projection capability](T014-native-public-projection-capability.md) | T002, T003, T004, T010, T011 | native public projection and action parity |
| T015 | DONE | [Public run context and controlled history](T015-public-run-context-and-controlled-history.md) | T002, T003, T004, T011, T014 | sanitized context and ordered history |
| T016 | DONE | [Public-context artifacts, replay, and audit](T016-public-context-artifacts-replay-and-audit.md) | T003, T004, T005, T011, T014, T015 | migrations, replay, and coverage audit |
| T017 | DONE | [Stable sts_lightspeed source integration](T017-stable-lightspeed-source-integration.md) | T004, T010, T014, T016 | external source manifest and verifier |
| T018 | DONE | [Native terminal resource identity surface](T018-native-terminal-resource-identity.md) | T012, T017 | native terminal potion/deck/relic/key identities |
| T019 | DONE | [Codebase mechanical refactor](T019-codebase-mechanical-refactor.md) | T001--T018 except cancelled T007 | CLI decomposition and export cleanup |
| T020 | DONE | [sts_lightspeed fork maintenance line](T020-sts-lightspeed-fork-maintenance.md) | T017 | single active fork integration branch |
| T021 | DONE | [A20 battle-start coverage measurement](T021-a20-battle-start-coverage-measurement.md) | T004, T005, T008, T009, T010, T012, T016, T017, T018, T020 | A20 natural/constructed coverage and broad-training gate gaps |
| T022 | DONE | [A20 Oracle teacher dataset report](T022-a20-oracle-teacher-dataset-report.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021 | Oracle-like teacher dataset coverage and source linkage |
| T023 | DONE | [A20 Oracle teacher dataset scale-up](T023-a20-oracle-teacher-dataset-scale-up.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021, T022 | structured Oracle-like teacher scale-up and budget stability |
| T024 | DONE | [Oracle teacher search-guidance training bridge](T024-oracle-teacher-search-guidance-training-bridge.md) | T003, T004, T006, T009, T011, T012, T016, T017, T018, T020, T021, T022, T023 | teacher-targeted trainer input and diagnostic checkpoint |
| T025 | DONE | [Search telemetry baseline](T025-search-telemetry-baseline.md) | T005, T006, T009, T017, T020, T024 | shared search telemetry and baseline cost reporting |
| T026 | DONE | [Guidance checkpoint inference contract](T026-guidance-checkpoint-inference-contract.md) | T009, T011, T016, T018, T024 | checkpoint scorer contract for search guidance |
| T027 | DONE | [Teacher guidance calibration report](T027-teacher-guidance-calibration-report.md) | T026 | offline checkpoint-vs-teacher calibration |
| T028 | DONE | [Model-guided Oracle search controller](T028-model-guided-oracle-search-controller.md) | T025, T026, T027 | first versioned model-guided Oracle-like search controller |
| T029 | DONE | [Fixed-cohort model-guided search comparison](T029-fixed-cohort-model-guided-search-comparison.md) | T025, T028 | equal-source/equal-budget fixed-cohort comparison |
| T030 | DONE | [M1 model-guided search sandbox synthesis](T030-m1-model-guided-search-sandbox-synthesis.md) | T027, T029 | milestone synthesis and next task batch |
| T031 | DONE | [A20 coverage refresh and data gap report](T031-a20-coverage-refresh-data-gap-report.md) | T030 | post-M1 A20 coverage refresh before broader teacher/checkpoint work |
| T032 | DONE | [A20 narrow teacher and checkpoint diagnostic refresh](T032-a20-teacher-checkpoint-refresh.md) | T039 | narrow T039 source-contract teacher, trainer-input, checkpoint, and calibration diagnostic |
| T033 | DRAFT | [Public context encoder contract](T033-public-context-encoder-contract.md) | T016, T030 | structured public history, map/route, visible-Boss encoder boundary |
| T034 | BLOCKED | [Public-consistent hidden-future sampler boundary](T034-public-consistent-hidden-future-sampler.md) | T033, native sampler support | normal-information hidden-future sampling substrate |
| T035 | DONE | [Model-guided Oracle search v2](T035-model-guided-oracle-search-v2.md) | T032, T025, T028, T029 | deeper Oracle-like guidance after refreshed data/checkpoint evidence |
| T036 | DONE | [A20 search-controlled reachability probe](T036-a20-search-controlled-reachability-probe.md) | T006, T017, T020, T025, T029, T031 | search-controlled source reachability after T031 Act-1 gap |
| T037 | DONE | [A20 search-controlled reachability scale-up](T037-a20-search-controlled-reachability-scaleup.md) | T017, T020, T036 | scaled reproduction of historical Boss/Act2 reachability evidence |
| T038 | CANCELLED | [A20 source drift audit](T038-a20-source-drift-audit.md) | T037 under-reachability result | not needed because T037 recovered Boss/Act2 reachability |
| T039 | DONE | [Later-act/Boss source coverage contract](T039-later-act-boss-source-coverage-contract.md) | T037 accepted source decision | explicit artifact contract before T032 can consume source coverage |
| T040 | READY | [Expert Non-Combat Driver v1](T040-expert-non-combat-driver-v1.md) | T010, T016, T017, T025, T036, T037, T039, T035 | A20 heuristic source-generation driver and coverage comparison |
| T041 | IN_REVIEW | [Potion-enabled Oracle search repair](T041-potion-enabled-oracle-search-repair.md) | T006, T017, T020, T025, T036, T037, T039 | repair potion root mapping and no-potion/potion cohort comparison |
| T042 | BLOCKED | [Assisted complete-run source generation](T042-assisted-complete-run-source-generation.md) | T040, T041 | assisted-run distribution, schedules, and coverage report |
| T043 | BLOCKED | [Assisted teacher dataset and value/policy training](T043-assisted-teacher-value-policy-training.md) | T042, T033 or finalized public-context model-input contract | assisted teacher data and public student diagnostics |
| T044 | BLOCKED | [De-assisted fixed-cohort evaluation](T044-de-assisted-fixed-cohort-evaluation.md) | T043 | low/no-assistance fixed-cohort model/search evaluation |

Use the table, not per-task files or roadmap prose, when deciding whether a
task may receive a branch. Only `READY` rows should receive a new branch. After
a prerequisite merges, the main maintainer reviews dependent specifications
against the new `main` before changing their state.

`BLOCKED` task specifications define intended boundaries but may be refined by
the main maintainer before becoming `READY`. Once a task is `READY`, its
published acceptance criteria are the review contract; scope changes require a
document update before acceptance.

## Task Boundary And Artifact Rules

Each task must have explicit, reviewable inputs and outputs. A prerequisite task
may provide a merged schema, command, fixture, or artifact-generation contract.
It does not provide an implicit local file dependency merely because a smoke run
left a checkpoint, trainer JSONL, report, or cohort in one worktree.

Required artifacts must be reproducible by documented commands, committed as
small fixtures, or supplied through an explicit external/ignored artifact path
with schema, provenance, compatibility requirements, and identity checks. A
task that needs an artifact from an earlier workflow must name that contract and
explain how a reviewer can regenerate or provide a compatible artifact.

Large generated artifacts remain outside the repository. The durable contract
is the schema, manifest/provenance, command surface, hashes where applicable,
and review evidence.

## Published Queue

The executable queue is the set of rows marked `READY` in the Active Backlog
table. A `READY` row may proceed in its own worktree and pull request based on
latest `main`.

## M1: Model-Guided Oracle Search Sandbox

M1's comparison target is now available: a reviewable fixed-cohort comparison
between the current Oracle-like native search baseline and the first
model-guided Oracle-like search controller using T024 teacher-targeted
checkpoint provenance. T030 completed the synthesis and next-task publication
work; T031 completed the post-M1 coverage refresh and found the current
distribution still Act-1-only. M1 is diagnostic search-engineering work only;
it must not claim
normal-information, live-game, broad-training, or promoted controller-strength
evidence.

Dependency chain:

```text
T025 search telemetry baseline --+
                                 +--> T028 model-guided Oracle search --> T029 fixed comparison --+
T026 checkpoint inference --> T027 teacher calibration -------------------------------------+
                                                                                              +--> T030 synthesis
```

The completed foundation backlog provides:

- fixed structural battle evaluation and Oracle-like search teacher plumbing;
- stable pinned `sts_lightspeed` source integration;
- raw native public projection, sanitized public context/history, artifact
  propagation, replay, and audit;
- structured battle resource outcomes and native terminal resource identities;
- conservative constructed A20 battle-start supplements;
- optional PyTorch policy/value plumbing, fail-closed broad-training gates,
  checkpoint provenance, and diagnostic smoke/narrow-curriculum training;
- current-schema A20 battle-start coverage reporting across natural, sampled,
  and constructed starts, including restore evidence and broad-training gate
  gaps;
- current-schema Oracle-like teacher dataset reporting with source-pool and
  optional T021 coverage linkage;
- structured Oracle-like teacher dataset scale-up with per-budget T022 reports
  and cross-budget teacher-label stability reporting;
- teacher-targeted trainer-input v6 conversion and diagnostic checkpoint
  provenance for selected T023 Oracle teacher budgets.
- first versioned model-guided Oracle-like search controller
  (`model_guided_oracle_search_v1`) that combines native root statistics with
  public checkpoint policy probabilities at root selection while preserving
  separate native-search and model-guidance telemetry.
- first versioned model-guided search fixed-cohort comparison report
  (`model-guided-search-fixed-comparison-v1`) that compares baseline Oracle
  search and model-guided Oracle-like search on identical restored starts with
  separate outcome aggregates, budget checks, and observed cost telemetry.

The T030 synthesis recommended the post-M1 batch as T031--T035. T031 refreshed
A20 coverage and diagnosed the current distribution gap: the artifacts and
restore path are healthy, but the current controller distribution produced no
Boss or later-act battle starts. T036 added current-schema search-controlled
complete-run source collection and a reachability report. Its accepted smoke
evidence kept all compared A20 arms in Act 1 only.

M2 is the A20 source-coverage recovery batch. T037 scaled the T036
search-controlled reachability path to the historical 1,000-run comparison
point and recovered the Boss/Act2 source signal on current schemas. T038 is
cancelled because the source-drift audit is not needed on that evidence. T039
accepted the durable T037 source-coverage contract. T032 completed the narrow
diagnostic refresh over that contract, not a broad A20 refresh. T035 completed
the next model-guided Oracle-like search experiment on refreshed diagnostic
checkpoint provenance; its accepted smoke comparison tied the baseline and T028
outcomes, so it is not promotion evidence.

M3 follows the upstream assisted source-generation guidance supplied after
T035. The milestone target is to generate broader, higher-quality A20
battle-state distributions before continuing broad neural training. T040 adds
a versioned A20 heuristic non-combat source-generation driver and remains
`READY`. T041 repairs the potion-enabled Oracle-like search failure and is
currently `IN_REVIEW`. T042 extends assistance into complete-run continuation
after those foundations merge. T043 turns assisted source pools into teacher
and public student diagnostics, and T044 evaluates de-assisted fixed cohorts.
T033 remains a public-context encoder draft, and T034 remains blocked on native
public-consistent hidden-future sampler support.

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
- native terminal resource identity coverage: T018;
- mechanical code cleanup and CLI/export decomposition: T019;
- `sts_lightspeed` fork integration-line maintenance: T020;
- A20 battle-start coverage measurement and broad-training gap reporting: T021.
- Oracle-like teacher dataset reporting and source linkage: T022.
- Structured Oracle-like teacher dataset scale-up and budget-stability
  reporting: T023.
- Teacher-targeted search-guidance trainer input and diagnostic checkpoint
  bridge: T024.
- M1 search telemetry and model-guided Oracle search sandbox: T025--T030.
- Post-M1 coverage, data, public-context, sampler, model-guided-search, and
  reachability follow-up proposals: T031--T039.
- Assisted source-generation curriculum: T040--T044.

T013 supplies the shared CommunicationMod adapter and captured-sample
compatibility gate. Simulator-only training experiments do not depend on it.
A trained or search controller still needs to use that adapter and earn its own
captured-sample or interactive evaluation evidence before it is described as
live-game validated.

CLI decomposition and command-module cleanup completed in T019. Feature tasks
may move only their own workflows out of CLI routing, following the
architecture contract, unless a later dedicated cleanup task explicitly
authorizes broader mechanical refactor.

Pure-Python linear scorer, policy-gradient, and policy-comparison experiments
from the legacy commit are explicitly unscheduled. They are preserved by the
legacy reference and may be published later only if they answer a concrete
research question.

New task documents should start from [`TEMPLATE.md`](TEMPLATE.md).
