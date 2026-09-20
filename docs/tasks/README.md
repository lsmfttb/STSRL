# Task Navigation

Task contracts are the durable specifications for one task. Read the
[`collaboration workflow`](../collaboration_workflow.md) before starting work.

This page is the short current/recent/parked navigation surface. The complete
durable lifecycle registry is [`ARCHIVE.md`](ARCHIVE.md); it preserves every
published or landed task ID, lifecycle state, contract link, and compact
historical lookup note without requiring the default reader to scan old
reports. This page is a convenience view, not lifecycle authority. Individual
task documents remain the authoritative contracts and retain their full
acceptance meaning.

## Reading order and authority

1. Planner operating memory lives in the [Planner Operating Dashboard issue
   #107](https://github.com/lsmfttb/STSRL/issues/107); research direction lives
   in the ledger issue [#85](https://github.com/lsmfttb/STSRL/issues/85).
2. The active task contract and its exact open PR form the current execution
   transaction. The unique approved open task PR is temporary authority until
   it lands.
3. [`../current_status.md`](../current_status.md) and the durable architecture
   documents describe accepted state on merged `main`.
4. [`ARCHIVE.md`](ARCHIVE.md), individual task contracts, experiment records,
   PRs, and Git history retain past reasoning and evidence.

The Issues are intentionally low-friction memory and operating surfaces; they
do not authorize implementation. The merged `ARCHIVE.md` registry is the
authority for landed lifecycle state; this README is convenience/derived
navigation only. A task's PR owns its exact execution, review, and approval
transaction.

## Selected contract navigation

Lifecycle states live only in [`ARCHIVE.md`](ARCHIVE.md). This table is a
stable shortcut to current contracts and planning context.

| ID | Task | Contract | Navigation |
|---|---|---|---|
| T034 | Public-consistent hidden-future sampler boundary | [contract](T034-public-consistent-hidden-future-sampler.md) | science: `current_status.md`; lifecycle/terminal: `ARCHIVE.md` |
| T063 | Oracle-guided public battle learning | [contract](T063-oracle-guided-public-battle-learning.md) | science: `current_status.md`; lifecycle/terminal: `ARCHIVE.md` |
| T066 | Alternating joint policy improvement and natural scale gate | [contract](T066-alternating-joint-policy-improvement-and-natural-scale-gate.md) | science: `current_status.md`; lifecycle/terminal: `ARCHIVE.md` |

## Recently completed

These rows provide stable contract shortcuts around the current boundary. The
full lifecycle row and terminal meaning for every task are in [`ARCHIVE.md`](ARCHIVE.md);
accepted science is summarized in [`../current_status.md`](../current_status.md).

| ID | Contract | Navigation |
|---|---|---|
| T089 | [Frozen-Search Self-Generated Non-Combat Policy Improvement](T089-frozen-search-self-generated-non-combat-policy.md) | current-status and archive result |
| T090 | [Search-v2 Action-Utility Battle Student](T090-search-v2-action-utility-battle-student.md) | current-status and archive result |
| T091 | [Battle Teacher Data-Surface Density Audit](T091-battle-teacher-data-surface-density-audit.md) | current-status and archive result |
| T092 | [Internal Search-State Teacher Data-Surface Gate](T092-internal-search-state-teacher-data-surface.md) | current-status and archive result |
| T093 | [Internal-State Partial-Ranking Public Battle-Student Distillation Gate](T093-internal-state-partial-ranking-battle-student.md) | current-status and archive result |
| T094 | [A-Cohort Supervision Attrition Decision Audit](T094-a-cohort-supervision-attrition-decision-audit.md) | current-status and archive result |
| T095 | [Repeated-Public-State Oracle Aggregation Feasibility Audit](T095-repeated-public-state-oracle-aggregation-feasibility.md) | current-status and archive result |
| T096 | [Battle Public-Information Hidden-Future Sampler Pilot](T096-battle-public-information-hidden-future-sampler-pilot.md) | current-status and archive result |
| T097 | [Native Visibility Capability Source Acceptance](T097-native-visibility-capability-source-acceptance.md) | current-status and archive result |
| T098 | [T096 Public-Information Fidelity Re-entry](T098-t096-public-information-fidelity-reentry.md) | current-status and archive result |
| T099 | [Native Particle-Search Bridge Source Acceptance](T099-native-particle-search-bridge-source-acceptance.md) | current-status and archive result |
| T100 | [Repository Information-Architecture Compaction](T100-repository-information-architecture-compaction.md) | this navigation repair and archive result |

## Lifecycle and review rules

The Current and Parked tables are convenience views, not a lifecycle database.
The merged archive in `main` is the single durable lifecycle registry; these
tables are derived navigation and may be stale or incomplete while a PR is in
flight. A task may be in flight before its candidate registry row lands: in
that case,
the unique open PR with exact-spec `SPEC APPROVED` and
`implementation_authorized=true` is temporary execution authority.

The Planner owns task meaning and scientific/architecture acceptance. The Main
Maintainer owns execution readiness, implementation/operational acceptance, and
repository conformance. The Implementer performs the authorized mechanical
work. Final acceptance requires both roles on the same exact final PR head;
Planner then lands the task. See the
[`collaboration workflow`](../collaboration_workflow.md) for the complete
authority and synchronization rules.

Task documents do not carry mutable `Status:` lines. `DRAFT`, `BLOCKED`,
`CANCELLED`, and terminal states retain their established meanings. Do not
renumber tasks, delete contracts, rewrite accepted terminal classifications,
or infer a successor from a historical result.

## Standard local gates

Unless a task contract says otherwise, use:

```text
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Task-specific simulator, artifact, and documentation checks are additional
requirements. Long-running WSL stages must report their effective workers,
shards, input ranges, wall time, and retained evidence; T100 starts no such
stage.

## Historical mapping

Use [`ARCHIVE.md`](ARCHIVE.md) for the complete compact mapping. Detailed
measurements and provenance remain in each task contract, retained report,
experiment record, PR, or Git history rather than being duplicated here.

New task contracts should start from [`TEMPLATE.md`](TEMPLATE.md). Future
task-specific support material belongs under `docs/tasks/support/Txxx/` when a
stable repository path is required; existing root-level paths remain valid
legacy references and are not being mass-migrated.
