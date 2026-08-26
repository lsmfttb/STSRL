# T065 Normative Appendix: Agent-Scope Documentation Alignment

This file is a normative specification appendix to
`T065-learned-non-combat-policy-v1.md`. It changes project-level terminology and
documentation boundaries only. It does not publish T065, authorize implementation,
or claim that a learned non-combat controller already exists on `main`.

## Why This Alignment Is Required

Current project contracts still contain an older battle-only scope statement,
including wording such as "battle-agent research infrastructure", "the current
trainable scope is battle decisions", and "non-combat decisions remain outside
the trainable agent". That wording accurately described an earlier project
phase, but it conflicts with the current training paradigm and with T065's
intended learned non-combat work.

The project boundary must therefore distinguish the complete agent from its two
decision subsystems instead of treating non-combat control as permanently
outside the trainable agent.

## Frozen Project Model

The intended project-level decomposition is:

```text
STSRL / complete A20 agent
|
+-- Battle Agent
|   +-- battle policy
|   +-- battle search
|   +-- learned policy/value guidance
|   +-- restored-battle training/evaluation
|
+-- Non-Combat Agent
|   +-- map/route decisions
|   +-- rewards and resource choices
|   +-- rest decisions
|   +-- treasure and other supported run decisions
|   +-- learned long-horizon action ranking/value
|
`-- Shared Run-Level Infrastructure
    +-- public run context and typed visible history
    +-- controller routing and decision contracts
    +-- simulator/checkpoint/replay boundaries
    +-- provenance and artifact contracts
    +-- run-continuation outcomes/value
    `-- complete-run evaluation
```

The final objective remains probability of defeating the Heart at Ascension 20
from a standard game start under the normal public information available to a
player.

Battle and non-combat control remain separate decision modules because their
horizons, action spaces, transition density, and useful search/learning methods
differ. They share the final run-level objective and the public run context, and
they are routed together only at complete-run execution/evaluation boundaries.

This decomposition does **not** require two repositories, two simulator stacks,
or duplicate provenance/evaluation systems.

## Battle Agent Boundary

The Battle Agent owns tactical battle decisions.

Its current primary direction remains search, with learned policy/value models
used mainly as search guidance or acceleration. Restored-battle curricula,
fixed-battle evaluation, Oracle-like battle search, battle policy/value targets,
and battle-specific search telemetry remain Battle Agent concerns.

Nothing in this appendix weakens the existing information-regime boundary:
Oracle-like full-state battle search remains training/diagnostic infrastructure,
not normal-information deployment evidence.

## Non-Combat Agent Boundary

The Non-Combat Agent owns player decisions outside battle, including routing,
reward/resource choices, rest, treasure, and later supported screen families.

The currently merged stochastic and `expert_non_combat_v1` implementations are
bootstrap/source-generation drivers. They are not evidence that a learned
non-combat agent is already implemented, and `expert_non_combat_v1` is not a
teacher label source.

T065 is the first proposed learned Non-Combat Agent experiment. Until T065 or a
successor is merged, current-status wording must continue to distinguish:

- implemented non-combat bootstrap drivers; from
- proposed/experimental learned non-combat policy capability.

Future non-combat learning may use simulator continuation value,
counterfactual action evaluation, public run-level values, and separately
justified non-combat search. It must not be forced through battle-specific model
or search abstractions merely because they already exist.

## Shared Run-Level Infrastructure Boundary

Shared infrastructure owns concerns that are not semantically battle-only or
non-combat-only:

- sanitized public decision context and complete visible run history;
- stable legal-action identity and generic controller/provenance contracts;
- routed complete-run execution;
- simulator identity, replay, checkpoint, and source-state contracts;
- run-level outcome/progression reporting;
- artifact identity and compatibility boundaries;
- matched complete-run evaluation.

Shared infrastructure must not collapse Battle Agent and Non-Combat Agent into a
single policy implementation. Conversely, subsystem code should not duplicate
shared run-context, replay, provenance, or evaluation contracts.

## Required Current-Document Alignment

When this appendix is accepted, the authoritative current documentation should
be brought into agreement with the frozen project model above.

### `README.md`

Replace the battle-only project identity with a complete-agent identity. The
entry point should communicate that STSRL researches a complete A20 Slay the
Spire agent composed of separate Battle Agent and Non-Combat Agent decision
modules over shared run-level infrastructure.

The current-capability section must remain factual: battle search/learning
infrastructure and non-combat bootstrap drivers are implemented; learned
non-combat control remains proposed until T065 is actually merged with valid
evidence.

### `docs/project_architecture.md`

Revise `Objective And Scope` so that the architectural target is the complete
A20 agent rather than a permanently battle-only trainable scope.

The existing battle search direction remains valid, but it must be described as
the Battle Agent direction rather than the whole-agent boundary.

Replace the current driver-only non-combat architectural wording with a
Non-Combat Agent / non-combat control section that:

- preserves seeded stochastic/bootstrap drivers as supported behavior policies;
- permits separately versioned learned non-combat controllers;
- keeps Battle Agent and Non-Combat Agent ownership distinct;
- keeps shared public run context and complete-run evaluation below/around both;
- does not claim T065 capability before merge.

### `AGENTS.md`

Remove the repository-wide rule that the trainable scope is permanently limited
to battle decisions.

Replace it with the invariant that Battle Agent and Non-Combat Agent are
separate trainable/controller modules sharing the final A20 objective and
run-level infrastructure. Coding agents must not put learned non-combat logic in
battle-specific modules solely for convenience.

Existing simulator, information-regime, dependency, artifact, and workflow
rules remain unchanged.

### `docs/current_status.md`

This file remains Maintainer-owned execution truth. Its goal wording should be
updated to the complete A20 agent objective, while its capability wording must
continue to say that learned non-combat control is not implemented until the
relevant task is merged.

A planning/specification PR must not rewrite current-status evidence as if T065
had already executed.

### `pyproject.toml`

Update only the package description from a battle-agent-only description to a
complete-agent research description when the documentation alignment is
published.

The distribution name `sts-combat-rl`, import package `sts_combat_rl`, and
existing console-script names remain historical/compatibility names for now.
Renaming them is explicitly out of scope because it would create broad churn
without changing the architecture.

## Historical Documents

Do not retrospectively rewrite completed task specifications, experiment reports,
or files under `docs/history/` merely because the project scope has expanded.
Statements that a past phase was battle-only are historical evidence and should
remain intact.

Battle-specific active/reference documents may also retain battle-specific names
when they genuinely describe only the Battle Agent subsystem.

The alignment target is current repository-wide contracts and entry-point
language, not historical narrative erasure.

## Acceptance Boundary For T065

T065 remains scientifically about the first learned Non-Combat Agent experiment.
This appendix does not add a new experimental stage, seed, model, cohort, gate,
or simulator run.

Before T065 implementation is considered complete, current repository-wide
project wording must no longer assert that non-combat decisions are permanently
outside the trainable agent. The final documentation must instead distinguish:

1. the complete A20 agent objective;
2. the Battle Agent subsystem;
3. the Non-Combat Agent subsystem;
4. shared run-level infrastructure; and
5. implemented capability versus proposed/experimental capability.

No package rename, repository split, duplicate infrastructure stack, or rewrite
of historical task documents is authorized by this appendix.
