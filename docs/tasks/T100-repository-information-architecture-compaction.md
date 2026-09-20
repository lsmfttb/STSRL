# T100: Repository Information-Architecture Compaction

Artifact Eligibility Required: false

## Objective

Reduce STSRL's default reading and maintenance surface without weakening scientific provenance, task semantics, review workflow, or Planner cross-session memory.

T100 is a repository-governance and documentation-maintenance task. It does not change research conclusions, simulator behavior, model/search behavior, experiment results, or accepted task semantics.

The target information lifecycle is:

```text
hot working memory
    -> active contract / execution transaction
    -> compact durable current state
    -> retained history
```

The intended roles are:

- Planner Operating Dashboard issue: concise high-visibility operating reminders and authority index;
- Planner research-direction ledger issue (#85): low-friction Planner working memory, research notes, direction changes, and cross-session continuity;
- task document: durable semantic contract for one task;
- task PR: exact in-flight implementation/review transaction;
- current durable docs: compact statement of what is true on merged `main`;
- historical task docs / experiment records / Git history: retained provenance and past reasoning.

T100 must preserve these distinct roles rather than collapsing Issues into repository docs or treating every information surface as the same kind of authority.

## Publication Baseline

Post-T099 publication base:

`main @ 80c4497b9901b7d9eb0cac456b416d5ce1ff9bcf`

T099 / PR #115 has landed with terminal:

`NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`

The previously planned bounded particle-count convergence task therefore moves to T101. T100 changes only repository governance/documentation before that scientific successor.

No T100 implementation is authorized until Maintainer reviews the exact post-T099 T100 spec head and records:

```text
SPEC APPROVED

task: T100
approved_spec_commit: <exact full SHA>
implementation_authorized: true
```

## Dependencies

- current merged collaboration workflow;
- current documentation guide;
- current task index and task contracts;
- current Planner Operating Dashboard issue;
- Planner research-direction ledger issue #85;
- accepted T099 landed state on `main @ 80c4497b9901b7d9eb0cac456b416d5ce1ff9bcf`.

## Current Scale Problem

The repository has reached a scale where several originally useful append-oriented surfaces are becoming costly default reading surfaces:

- `docs/tasks/README.md` contains roughly one hundred task lifecycle rows;
- `docs/tasks/` contains more than one hundred task-related files;
- `docs/current_status.md` has grown into a long mixed current-state and historical narrative;
- `docs/` root mixes long-lived contracts, operations guides, research plans, historical handoffs, and task-specific support material.

The problem is not loss of provenance. The problem is that current navigation surfaces increasingly require readers and agents to scan historical material that is no longer needed to answer "what is true now?" or "what is the active task?"

T099 also exposed a separate workflow defect: the repository current-state record was asked to say that final acceptance was still pending on the same head that then had to receive final acceptance and be merged. That creates a self-invalidating loop unless transient PR state and merge-stable repository state are explicitly separated.

## Scope

### 1. Preserve and formalize the two Planner Issue roles

Do not remove or demote the two Planner-facing Issues.

#### Planner Operating Dashboard

Use as a concise operating/startup card:

- Planner role boundary;
- blocker test;
- final-acceptance trigger discipline;
- anti-patch-loop reminder;
- links to durable authorities.

It remains intentionally easier to read than the full collaboration workflow and must not become a second complete copy of repository governance.

#### Planner research-direction ledger (#85)

Use as the Planner's research working memory:

- rapid notes from Planner/user discussion;
- new hypotheses before they are mature enough for a task;
- reasons for direction changes;
- explicit route closure/weakening;
- successor reasoning;
- cross-session context recovery.

The Issue comment stream may remain append-oriented.

The Issue body should function as a periodically compacted current research map rather than an immutable historical snapshot. Historical reasoning remains available in comments.

The ledger does not itself authorize implementation. Durable task meaning enters the task/PR workflow when work is published.

### 2. Compact `docs/current_status.md` into a true current-state document

Rewrite `docs/current_status.md` so its primary job is to answer:

> what is the accepted project state on merged `main` now?

It should emphasize:

- project goal and deployment information boundary;
- accepted runtime/native baseline;
- strongest accepted current baselines/capabilities;
- current scientific diagnosis;
- active blocker or active task;
- closed routes summarized by conclusion plus links;
- immediate successor decision boundary;
- parked long-term directions.

Do not preserve historical narrative merely because it was once appended to this file.

Past task results remain recoverable from task contracts, PRs, experiment records, the research ledger, and Git history.

No scientific conclusion may be silently changed during compaction. If old wording conflicts with a later accepted result, the compact current document must use the later accepted result and link to its provenance.

### 3. Separate merge-stable project state from transient PR transaction state

This is a required workflow repair, not an optional wording cleanup.

Repository current-state documents must contain **merge-stable facts**: statements that remain true if the reviewed head is accepted and merged.

Examples of merge-stable repository facts:

- exact accepted source identities;
- accepted capability/result terminal;
- limitations and nonclaims;
- retained evidence identity/location where durable;
- immediate scientific successor boundary;
- factual implementation result that the candidate head would contribute to `main`.

Transient transaction state belongs to the PR/Issue transaction timeline, not `docs/current_status.md` or another durable current-state document.

Examples of transient PR state:

- "pending Maintainer review";
- "waiting for Planner acceptance";
- "final candidate awaiting merge";
- "SPEC APPROVED";
- implementation authorization;
- Maintainer final acceptance;
- Planner final acceptance;
- merge readiness.

The collaboration workflow must explicitly distinguish:

1. **merge-stable landed-state projection** recorded in repository files before final exact-head review; and
2. **transient approval/lifecycle state** recorded on the PR.

Maintainer may update repository current-state/result records before final dual acceptance, but that text must be written as the state the exact head contributes if landed, not as a live narration of who still needs to approve it.

A final acceptance must not require a repository edit whose only purpose is to change "pending acceptance" into "accepted", because that edit changes the exact head and can recursively invalidate the acceptance.

Task docs may retain candidate-result sections when useful, but transient approval state must not be required as durable repository truth.

### 4. Split active task navigation from full task history

Refactor `docs/tasks/README.md` so it is an efficient current navigation surface rather than a mini-report database for every historical task.

The default task index should prioritize:

- active/in-flight task state;
- published drafts/parked directions;
- recently completed tasks sufficient for local context;
- links to full historical task index/history.

Create or maintain a compact durable historical index, for example `docs/tasks/ARCHIVE.md`, that preserves:

- task ID;
- lifecycle state;
- title/link;
- minimal dependency/provenance information where still useful;
- terminal label when it materially improves historical lookup.

Historical index rows should not duplicate detailed experimental reports already present in task documents.

Do not renumber tasks. Do not remove historical task documents.

### 5. Reduce duplication between task contract and PR transaction

Clarify that:

- task document owns durable task meaning;
- PR owns exact execution/review state.

Future PR descriptions/comments should prefer references to the approved task contract rather than repeating long sections of:

- task scope;
- prohibitions;
- scientific semantics;
- terminal meaning.

PRs must still record exact identities needed for transaction safety, including relevant base/head/approval/final-acceptance SHAs.

This simplification must not weaken exact-head review or dual final acceptance.

### 6. Improve documentation navigation without a mass link-breaking migration

Update `docs/README.md` to make the information lifecycle and default reading order obvious.

Define placement rules for future documents so new task-specific support material does not continue accumulating at `docs/` root.

A preferred pattern may be introduced for future support files, such as:

```text
docs/tasks/support/Txxx/
```

or an equivalent clearly documented location.

Do not perform a large historical file move solely for visual cleanliness if it would create widespread link churn or break old PR/task references.

Existing stable paths may remain as legacy locations. The goal is to stop future root-level sprawl and improve navigation, not rewrite repository history.

### 7. Preserve authority boundaries

The compaction must retain these distinctions:

- merged `main` remains durable landed project truth;
- task semantics remain in task documents;
- the exact approved open task PR remains temporary execution authority under the collaboration workflow;
- Planner Issues are low-friction memory/operating surfaces, not implementation authorization;
- architecture/governance documents remain authoritative for repository-wide rules;
- historical documents do not override current durable documents.

## Out Of Scope

T100 must not:

- change T099 scientific meaning or accepted result;
- run the particle-count convergence experiment;
- change native source identity;
- change Battle/Search/model behavior;
- alter accepted scientific result numbers;
- renumber historical tasks;
- delete historical task contracts;
- rewrite accepted terminal classifications;
- merge the Planner research ledger into repository docs;
- remove the Planner Operating Dashboard;
- create a new parallel project-management database;
- weaken exact-head review or dual final acceptance;
- perform a broad code refactor unrelated to documentation/governance maintenance.

## Design Constraints

### Low-friction memory is intentional

Do not force every Planner thought into a repository PR.

The Planner research ledger exists specifically because changing an Issue is lower-friction than changing the repository and is useful during long conversations or Planner handoffs.

### Current docs must be compact

A document named `current_status.md` should not require reading the full history of the project to recover the current state.

### Current docs must be merge-stable

Durable current-state files must not depend on the instantaneous approval phase of an open PR.

### History must remain recoverable

Compaction may remove historical narrative from current surfaces, but historical meaning must remain recoverable through existing task documents, PRs, issues, experiment records, or Git history.

### Avoid duplicate normative sources

Short reminders may intentionally repeat critical rules for usability, especially in the Planner Dashboard, but the reminder must link to and defer to its durable authority.

### Prefer minimal migration churn

Do not move large numbers of old files merely to create an aesthetically perfect directory tree.

## Deliverables

At minimum:

1. revised `docs/current_status.md` with a compact current-only and merge-stable structure;
2. revised `docs/tasks/README.md` optimized for active/recent navigation;
3. compact historical task index if needed to retain easy full-task lookup;
4. revised `docs/README.md` explaining:
   - hot Planner memory;
   - active task/PR transaction;
   - durable current docs;
   - history;
5. collaboration/governance wording updated to:
   - preserve the two Planner Issue roles;
   - distinguish merge-stable repository state from transient PR state;
   - prevent self-invalidating final-acceptance edits;
6. a documented placement rule for future task-specific support docs;
7. focused tests/guards updated only if existing tests incorrectly require the old unbounded documentation shape.

## Acceptance Criteria

T100 passes only if:

- the Planner Operating Dashboard remains a concise high-visibility operating entry point;
- #85 remains an explicitly supported low-friction research working-memory surface;
- Issue use is not redefined as an error or merely deprecated duplication;
- `current_status.md` is materially smaller and clearly current-state-oriented;
- durable current-state wording is merge-stable and does not encode transient PR approval/merge phase;
- the collaboration workflow assigns transient acceptance/lifecycle state to the PR transaction layer;
- final exact-head acceptance no longer creates a required follow-up repository edit solely to replace "pending" wording;
- the default task README no longer requires scanning detailed mini-reports for the entire historical task sequence;
- every historical task remains discoverable by ID and linked to its task contract;
- historical task IDs and accepted terminal meanings are preserved;
- documentation reading order clearly distinguishes hot memory, active transaction, current durable truth, and history;
- no accepted scientific conclusion is changed;
- no implementation authorization rule, exact-head review rule, or final dual-acceptance rule is weakened;
- no large historical path migration is required merely for cosmetic cleanup;
- repository documentation/tests remain internally consistent.

## Required Verification

Run ordinary documentation/repository gates appropriate to the changed files, including:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
```

Also run focused documentation/task-index guards.

Implementation must report:

- before/after line or byte counts for the major compacted navigation surfaces;
- confirmation that every historical task ID remains discoverable;
- checks for broken internal documentation references when supported by repository tooling;
- any intentionally retained legacy root-level docs and why they were not moved;
- a focused check that durable current-state docs do not contain transient approval-phase phrases for the active task.

No simulator-scale execution is required.

## PR Report

The final PR report should include:

- exact synchronized post-T099 base;
- documentation surfaces changed;
- before/after size summary;
- historical lookup preservation;
- Planner Issue role preservation;
- workflow wording changed for merge-stable vs transient state;
- any path migrations performed;
- focused/full gate results;
- confirmation that no scientific/task semantics were changed.

## Success Meaning

Successful T100 means:

`REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`

This terminal means the repository has a lower-cost default reading/navigation surface while retaining low-friction Planner memory, exact task provenance, historical recoverability, and a non-self-invalidating final-acceptance workflow.

It does not authorize or imply any scientific result.

## Implementation record

The documentation projection is based on the synchronized post-T099 base
`80c4497b9901b7d9eb0cac456b416d5ce1ff9bcf`. The major navigation surfaces were
compacted as follows:

| Surface | Before | After |
|---|---:|---:|
| `docs/current_status.md` | 2,504 lines / 166,161 bytes | 159 lines / 8,363 bytes |
| `docs/tasks/README.md` | 410 lines / 45,088 bytes | 129 lines / 8,341 bytes |
| `docs/tasks/ARCHIVE.md` | not present | 128 lines / 19,514 bytes |

The archive retains every published task ID and primary contract link, plus
the additional T065 and T087 same-ID contract/amendment files. Internal
Markdown paths resolve, and the durable current-state guard contains no
approval-phase wording. Planner Dashboard issue #107 and research ledger #85
remain external low-friction memory surfaces; no Issue content was copied into
the repository and neither role was removed or deprecated.

The ordinary repository checks completed with these environment-bound results:
`compileall` passed; both mock fixtures passed; the focused workflow-document
tests passed 3/3; the supported pytest run passed 1,285 tests with 31 skips and
10 repository-baseline/environment failures. Full pytest collection additionally
lacks optional Torch and Windows `resource` support. Full Ruff check/format
retain existing repository-wide diagnostics. T100 made no runtime, native, simulator, model,
Search, training, or scientific-result change and performed no path migration.

## Successor

After T100 lands without changing the scientific queue, Planner may publish the bounded particle-count convergence task as T101.

T100 must not pre-specify that experiment beyond preserving the already accepted ordering and claim boundary.

## Authorization Boundary

T100 is now the unique next STSRL maintenance task candidate.

A task implementation requires Maintainer review of the exact task-specification
head and an exact-head `SPEC APPROVED` record with
`implementation_authorized=true`. The PR transaction records whether this
requirement is satisfied for a given head; this task contract does not narrate
that transient state.

Any material change to:

- the Issue-role split;
- merge-stable versus transient-state ownership;
- task-history retention guarantees;
- exact-head/final-acceptance workflow;
- T101 successor ordering

requires Planner amendment and renewed Maintainer exact-spec approval.
