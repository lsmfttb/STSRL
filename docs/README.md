# Documentation Guide

This directory separates current contracts, current status, active roadmaps,
operational guides, and historical records. A document's role determines how
it should be used during implementation and review.

## Authority Order

When documents disagree, use this order:

1. [`../AGENTS.md`](../AGENTS.md): concise repository-wide contributor rules.
2. [`project_architecture.md`](project_architecture.md): authoritative design
   and ownership boundaries.
3. [`current_status.md`](current_status.md): implemented capabilities, known
   gaps, and current priorities.
4. Active roadmap documents: intended future work within the architecture.
5. Operational guides: commands and environment details.
6. [`history/`](history/README.md): past investigations and superseded plans.

`README.md` is the project entry point, not an exhaustive specification.

## Current Documents

### Contract

- [`project_architecture.md`](project_architecture.md): controller boundaries,
  information regimes, data provenance, objectives, artifact migration, and
  code ownership.
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
  roles, one-task-one-branch workflow, task specification contract, review, and
  merge process.
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

- Put repository-wide invariants only in `project_architecture.md` and summarize
  the most important ones in `AGENTS.md`.
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

`main` is the only integration line. Concrete work begins only from a `READY`
task under `tasks/`, and each task receives one fresh branch and one pull
request based on latest `main`. See `collaboration_workflow.md`; do not infer
workflow from old branch names or historical documents.
