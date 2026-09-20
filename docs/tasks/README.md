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
do not authorize implementation. Merged `main` remains the durable authority
for landed lifecycle state. A task's PR owns its exact execution, review, and
approval transaction.

## Current and parked navigation

| ID | State | Task | Contract | Boundary |
|---|---|---|---|---|
| T034 | BLOCKED | Public-consistent hidden-future sampler boundary | [contract](T034-public-consistent-hidden-future-sampler.md) | native public-consistent hidden-future support remains the blocker |
| T063 | DRAFT | Oracle-guided public battle learning | [contract](T063-oracle-guided-public-battle-learning.md) | simulator-only Oracle assistance; no human trajectories |
| T066 | DRAFT | Alternating joint policy improvement and natural scale gate | [contract](T066-alternating-joint-policy-improvement-and-natural-scale-gate.md) | separate battle/non-combat policies; not authorized by prior work |

The next scientific successor after the documentation maintenance boundary is
T101, the separately specified bounded particle-count convergence task. T100
does not publish, authorize, or pre-specify that experiment.

## Recently completed

These rows provide local context around the current boundary. The full row for
every task is in [`ARCHIVE.md`](ARCHIVE.md).

| ID | State | Contract | Durable result |
|---|---|---|---|
| T089 | DONE | [Frozen-Search Self-Generated Non-Combat Policy Improvement](T089-frozen-search-self-generated-non-combat-policy.md) | `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`; no promotion or T066 continuation |
| T090 | DONE | [Search-v2 Action-Utility Battle Student](T090-search-v2-action-utility-battle-student.md) | `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT`; no training or promotion |
| T091 | DONE | [Battle Teacher Data-Surface Density Audit](T091-battle-teacher-data-surface-density-audit.md) | `ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED`; internal surface remains feasible |
| T092 | DONE | [Internal Search-State Teacher Data-Surface Gate](T092-internal-search-state-teacher-data-surface.md) | `INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH`; no Search change or student claim |
| T093 | DONE | [Internal-State Partial-Ranking Public Battle-Student Distillation Gate](T093-internal-state-partial-ranking-battle-student.md) | `INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT`; no training or integration |
| T094 | DONE | [A-Cohort Supervision Attrition Decision Audit](T094-a-cohort-supervision-attrition-decision-audit.md) | `A_COHORT_CANONICALIZATION_LIMITING`; no Search or controller rerun |
| T095 | DONE | [Repeated-Public-State Oracle Aggregation Feasibility Audit](T095-repeated-public-state-oracle-aggregation-feasibility.md) | `EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE`; no aggregation or scientific promotion |
| T096 | DONE | [Battle Public-Information Hidden-Future Sampler Pilot](T096-battle-public-information-hidden-future-sampler-pilot.md) | `NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`; fidelity gaps remain explicit |
| T097 | DONE | [Native Visibility Capability Source Acceptance](T097-native-visibility-capability-source-acceptance.md) | `NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED`; reproducible native capability input |
| T098 | DONE | [T096 Public-Information Fidelity Re-entry](T098-t096-public-information-fidelity-reentry.md) | `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`; no convergence or controller claim |
| T099 | DONE | [Native Particle-Search Bridge Source Acceptance](T099-native-particle-search-bridge-source-acceptance.md) | `NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`; mixed bridge capability only |
| T100 | DONE | [Repository Information-Architecture Compaction](T100-repository-information-architecture-compaction.md) | `REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`; no scientific or runtime change |

## Lifecycle and review rules

The Current and Parked table is a convenience view, not a lifecycle database.
The merged archive in `main` is the single durable lifecycle registry; this page
is derived navigation and may be stale or incomplete while a PR is in flight.
A task may be in flight before its candidate registry/navigation rows land: in
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

## Current planning direction

STSRL remains a simulator-only self-generated policy-improvement project with
separate Battle and Non-Combat decision modules and training-time Oracle
assistance. See [`../training_paradigm.md`](../training_paradigm.md) and
[`../current_status.md`](../current_status.md) for current boundaries.

T088 freezes unguided Search v2 @400 as the strongest accepted non-learned
Battle baseline on the matched Battle-start distribution. T089 did not
establish learned Non-Combat improvement. T090--T095 diagnose supervision and
aggregation limits without changing Search or promoting a student. T096--T099
establish the accepted native visibility and particle/Search bridge inputs;
they do not claim convergence, posterior exactness, or controller improvement.

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
