# Documentation Guide

This directory separates current contracts, current status, active roadmaps,
operational guides, and historical records. A document's role determines how
it should be used during implementation and review.

## Authority Order

Use the document that owns the question rather than duplicating rules across
several files:

1. [`../AGENTS.md`](../AGENTS.md): concise repository-wide contributor rules.
2. [`project_architecture.md`](project_architecture.md): runtime, model, data,
   information-regime, and code-ownership architecture.
3. [`training_paradigm.md`](training_paradigm.md): authoritative training-signal
   and human-knowledge boundary.
4. [`collaboration_workflow.md`](collaboration_workflow.md): authoritative task
   roles, Planner-owned design/acceptance semantics, branch/PR workflow,
   execution authorization, escalation, and review/merge process.
5. [`research_inspirations_and_attribution.md`](research_inspirations_and_attribution.md):
   research lineage, attribution, and publication-time third-party licensing
   requirements.
6. [`current_status.md`](current_status.md): implemented capabilities, known
   gaps, and current priorities.
7. Active roadmap documents: intended future work within the architecture.
8. Operational guides: commands and environment details.
9. [`history/`](history/README.md): past investigations and superseded plans.

`README.md` is the project entry point, not an exhaustive specification.

## Current Documents

### Contract

- [`project_architecture.md`](project_architecture.md): controller boundaries,
  information regimes, data provenance, objectives, artifact migration, and
  code ownership.
- [`training_paradigm.md`](training_paradigm.md): simulator-only self-generated
  improvement, Oracle-assistance rules, final human-knowledge boundary, and
  distribution contract.
- [`research_inspirations_and_attribution.md`](research_inspirations_and_attribution.md):
  explicit AlphaZero/Suphx citations, CombatSolver attribution, source-use
  boundary, and public-release checklist.
- [`a20_later_act_boss_source_coverage_contract.md`](a20_later_act_boss_source_coverage_contract.md):
  accepted T037 source-coverage boundary for narrow Boss/later-act follow-up
  work.

### Status

- [`current_status.md`](current_status.md): concise state of implementation and
  immediate work.
- [`tasks/README.md`](tasks/README.md): executable task backlog, dependencies,
  and readiness.
- [`m1_model_guided_search_sandbox_synthesis.md`](m1_model_guided_search_sandbox_synthesis.md):
  M1 evidence synthesis and post-M1 task-batch recommendation.
- [`experiment_log.md`](experiment_log.md): curated dated results. Results
  explain evidence; they do not create architectural rules.

### Collaboration

- [`collaboration_workflow.md`](collaboration_workflow.md): authoritative
  Planner/Maintainer/Implementer responsibility split, one-task-one-branch
  workflow, acceptance-first contract, contract-gap escalation, architecture
  recovery, dual final acceptance, and merge process.
- [`sts_lightspeed_maintainer_role.md`](sts_lightspeed_maintainer_role.md):
  operating contract for the external `sts_lightspeed` fork maintainer role,
  branch policy, cross-repository handoff, and review evidence.

### Active Roadmaps

- [`battle_dataset_search_and_sl_plan.md`](battle_dataset_search_and_sl_plan.md):
  dataset distributions, evaluation, search development, and the separately
  evaluated SL-enabled branch.
- [`normal_information_search_and_resource_value_plan.md`](normal_information_search_and_resource_value_plan.md):
  normal-information search, Oracle-to-normal transfer, complete public run
  context, and continuation value.

### Operations

- [`sts_lightspeed_wsl_spike.md`](sts_lightspeed_wsl_spike.md): current external
  simulator setup, pinned source manifest, and verification commands.

### History

- [`history/README.md`](history/README.md): index of simulator comparisons,
  rejected spikes, and the superseded first trainer plan.

## Maintenance Rules

- Put repository-wide runtime/design invariants in `project_architecture.md` and
  summarize the most important ones in `AGENTS.md`.
- Put training-signal and human-knowledge rules in `training_paradigm.md`.
- Keep research citations, attribution, and publication-time source-use checks
  in `research_inspirations_and_attribution.md`.
- Put task ownership and execution/review workflow in
  `collaboration_workflow.md`; keep other summaries short and consistent with
  it.
- Update `current_status.md` when implementation capability or the immediate
  blocker changes.
- Put future design in the relevant roadmap; do not mix dated experiment
  narratives into roadmaps.
- Put dated measurements in `experiment_log.md`.
- Move superseded plans to `history/` instead of leaving contradictory current
  instructions in place.
- Prefer links over duplicating long commands, measurements, or design
  arguments across several files.

## Branch Workflow

`main` is the only integration line. For a new task, the Planner creates one
fresh branch and one draft pull request from current `main`, writes an
implementer-ready contract including the scientific/architectural design and
normative acceptance boundary, and owns any later contract-gap resolution. The
Main Maintainer checks repository/execution readiness, authorizes and coordinates
the bounded implementation, classifies review findings, and returns semantic or
architectural gaps to the Planner instead of inventing local rules. The Task
Implementer performs the mechanical implementation against the frozen contract.
Before merge, the exact final head requires Planner scientific/architectural
acceptance plus Maintainer implementation/operational acceptance; the Maintainer
then owns merge and the `current_status.md` result report. Merged task lifecycle
remains authoritative in `tasks/README.md`.

Before branch creation or execution readiness, the Maintainer must fetch the
configured upstream `main` ref and verify exact full-SHA equality with local
`main`; immediately before landing, repeat the fetch and compare the recorded
pre-landing base SHA with remote `main`, requiring a fast-forward. A failed
fetch or any ahead/behind/divergent state blocks the work. See the detailed
[`Main Synchronization Gate`](collaboration_workflow.md#main-synchronization-gate).

See `collaboration_workflow.md` for the complete contract; do not infer workflow
from old branch names, historical documents, or stale role summaries.
