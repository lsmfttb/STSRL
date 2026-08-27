# T065 Documentation Impact Note: Agent-Scope Terminology

This file records a **documentation impact for Main Maintainer follow-up**. It is
not a T065 implementation acceptance requirement, it is not a current-main
architecture contract, and it does not authorize the Implementer to rewrite
`README.md`, `AGENTS.md`, `docs/project_architecture.md`,
`docs/current_status.md`, or `pyproject.toml` by interpretation.

T065 remains scientifically about a learned non-combat policy experiment. The
current project documentation may continue to describe the *currently merged*
trainable capability as battle-first while T065 is unmerged. This note exists so
that the project vocabulary can be reconsidered factually after T065 produces a
terminal result.

## Proposed Future Terminology

When the Main Maintainer next updates project-level scope after T065 or a
successor establishes an accepted learned non-combat capability, the preferred
conceptual decomposition is:

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
from a standard game start under normal public information.

The intent is **separate Battle Agent and Non-Combat Agent ownership inside one
repository and one shared infrastructure stack**. It does not imply two
repositories, duplicated simulator/provenance/evaluation systems, or a package
rename.

## Current Capability Must Remain Factual

Before a learned non-combat task is merged with valid evidence, current-status
language must continue to distinguish:

- merged stochastic / `expert_non_combat_v1` bootstrap and source-generation
  drivers; from
- proposed or experimental learned non-combat capability.

This note therefore does not claim that T065 exists on `main`, that a learned
Non-Combat Agent has been promoted, or that current status is already wrong
merely because it says the *current* trainable capability is battle-focused.

## Maintainer-Owned Follow-Up

After T065 reaches a terminal Case A/B/C/D and before publishing a later roadmap
that relies on a broader project identity, the Main Maintainer should decide
whether factual current documentation now warrants scope-language changes.
Possible files to review are:

- `README.md`;
- `docs/project_architecture.md`;
- `AGENTS.md`;
- `docs/current_status.md`;
- the `pyproject.toml` description.

If such an update is warranted, the Maintainer should preserve the distinction
between project objective, subsystem architecture, and actually implemented /
promoted capability. The Implementer for T065 is not required or authorized by
this note to perform those project-level edits.

The distribution name `sts-combat-rl`, import package `sts_combat_rl`, and
existing console-script names should remain historical/compatibility names
unless a separately reviewed migration is justified.

## Historical Documents

Do not retrospectively rewrite completed task specifications, experiment reports,
or files under `docs/history/`. Battle-specific documents may remain explicitly
battle-specific when that is their actual subject.

This note changes no T065 seed, model, cohort, gate, simulator run, acceptance
criterion, lifecycle state, or scientific claim.