# T102: Structured Agent-to-Planner Notification and Attribution Protocol

Artifact Eligibility Required: false

## Objective

Establish a repository-wide protocol that allows authorized project Agents to
proactively notify Planner when Planner action is required, without requiring
the user to relay ordinary review requests and without allowing notification
traffic to become a second authority channel or an unbounded Planner-context
stream.

T102 addresses a workflow problem, not a scientific one:

> Agent -> Planner communication should be fast enough to remove routine human
> relay, while remaining attributable, idempotent under retry/duplicate
> delivery, bounded in payload, and explicitly non-authoritative until Planner
> independently verifies durable repository evidence and records the required
> decision.

The protocol must work even when:

- network retry delivers the same logical request more than once;
- more than one Planner conversation/branch receives the same request;
- a prior Planner branch completed work but its chat record is unavailable;
- several cooperating Agents share the same GitHub account or repository
  credentials;
- the receiving Planner has little or no prior conversational context.

T102 is motivated in part by the attribution ambiguity observed around T101
PR #117. That event is **not** classified as a confirmed unauthorized merge or
Agent impersonation. A plausible explanation is duplicate request delivery /
conversation branching. T102 treats it as an idempotency and attribution
problem.

## Publication Baseline

Planner publication base:

`main @ 1b9fd53b8708c0c328a795ca7ad87d4fe4648b99`

At publication there are no open task PRs.

Accepted governance predecessors:

- T100: `REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`.

T102 is documentation/governance work only. It does not change simulator,
native, Search, training, scientific-result, artifact-eligibility, or task
terminal semantics.

## Core Principle

**Agent -> Planner communication is notification, not authority.**

A notification may wake or route Planner to a durable review request. It must
not itself:

- approve a task specification;
- authorize implementation;
- grant canary/formal scientific execution;
- record Maintainer final acceptance;
- record Planner final acceptance;
- change scientific interpretation or successor meaning;
- authorize a merge;
- create a second task/lifecycle registry.

Authority continues to come from the existing workflow and durable exact-head
records.

A role string inside a message is a routing claim, not cryptographic identity.
T102 does not claim to solve cryptographic Agent authentication.

## Authorized Routing

T102 must preserve the existing role hierarchy.

### STSRL

Default route:

```text
Task Implementer -> Main Maintainer -> Planner
```

The STSRL Task Implementer does not bypass the Main Maintainer merely because a
direct Planner messaging mechanism exists.

The Main Maintainer may proactively notify Planner when Planner action is
actually required, including:

- exact-spec review after task publication or material contract amendment;
- a genuine semantic/architecture gap classified as requiring Planner decision;
- final scientific/architecture review after Maintainer final acceptance;
- an exceptional landing/authority ambiguity that the workflow explicitly
  assigns to Planner.

Routine implementation progress, test logs, canary progress, operational
diagnostics, and Maintainer-owned execution choices do not justify Planner
notification.

### External native lane

When an accepted cross-repository workflow explicitly assigns Planner an
independent semantic/source-acceptance review, the designated
`sts_lightspeed` Implementer or reviewer may notify Planner directly.

That direct notification does not bypass any native-repository review or merge
requirements and does not convert the sender into Planner authority.

### User

The user may always request Planner review manually. Manual user relay remains
valid and is not prohibited by T102.

If a manual request and an Agent notification refer to the same durable review
request, Planner should converge them through the same deduplication rules
rather than perform two independent reviews.

## Durable-Source-First Notification

Every automated Agent -> Planner notification must be anchored in a durable
repository request **before** direct delivery.

For a task PR, the sender must first post a concise GitHub PR comment containing:

- protocol version;
- sender role;
- repository;
- task ID;
- PR number;
- phase;
- exact PR head;
- requested Planner action;
- short material-delta summary;
- durable evidence locations;
- explicit statement that the notification is non-authoritative.

The GitHub comment ID is the notification's durable identity:

```text
notification_id = github-pr-comment:<comment_id>
```

Transport retry must reuse the same `notification_id`; it must not create a
new PR request comment merely because direct delivery timed out or is uncertain.

If the exact head, requested Planner action, or material evidence boundary
changes, the sender posts a new durable request comment and therefore receives
a new notification ID.

Do not use an issue, chat message, or in-memory Agent thread as the sole source
of a Planner review request when a task PR exists.

## Direct Notification Envelope

The direct Agent -> Planner message must be a compact envelope, not a copied
review packet.

Required fields:

```text
PLANNER_NOTIFICATION
protocol_version: agent-planner-notification-v1
notification_id: github-pr-comment:<id>
sender_role: <role>
repository: <owner/repo>
task: <Txxx or native work item>
pull_request: <number/url>
phase: <SPEC_REVIEW | MATERIAL_DECISION | FINAL_REVIEW | NATIVE_REVIEW | EXCEPTION>
exact_head: <40-char SHA>
requested_action: <one concise action>
material_delta: <short summary>
evidence_anchor: <durable PR comment URL/id>
authority: notification_only
```

Optional fields may include:

- supersedes notification ID;
- relevant native PR/head;
- one concise blocker code;
- one concise note that the user manually requested the same review.

The direct message should normally contain no raw test log, full diff, large
artifact dump, or long scientific argument. Planner retrieves those from the PR
and repository as needed.

## Context-Budget Rule

Automated notification payloads must be intentionally small.

The protocol should prefer:

- exact identifiers;
- one short material-delta summary;
- durable evidence links/IDs;
- one requested action.

It should avoid:

- copied full comments already present on GitHub;
- repeated task history;
- complete test output;
- speculative analysis not needed to route the review;
- routine progress updates.

The authoritative review context remains the repository, PR, retained artifacts,
and exact commits, not the notification message.

## Duplicate Delivery And Planner-Branch Convergence

T102 must explicitly handle the case in which the same notification reaches two
Planner conversations.

Before substantive review, Planner must:

1. fetch and validate the durable notification comment;
2. verify repository/task/PR/exact-head consistency;
3. check whether an accepted Planner decision already exists for the same
   notification ID / exact-head request;
4. if already resolved, do not repeat the decision or merge action.

If unresolved, Planner records a lightweight PR receipt:

```text
PLANNER_REVIEW_RECEIPT

notification_id: github-pr-comment:<id>
exact_head: <sha>
review_nonce: <opaque per-conversation nonce>
status: CLAIMED
```

Planner then re-fetches receipts for that notification ID.

If multiple receipts exist because duplicate Planner branches raced, the
receipt with the lowest GitHub comment ID is the deterministic review owner.
Other Planner branches stop before recording acceptance, rejection, task
amendment, or merge.

The losing branch may report that the request is already claimed/resolved, but
must not create competing Planner authority.

This receipt is coordination metadata only. It is not scientific acceptance or
merge authorization.

### Lost review-owner recovery

The deterministic receipt owner must not be silently stolen merely because a
chat turn is slow, disconnected, or no longer visible.

If the owning Planner conversation is genuinely unavailable before recording an
authoritative decision, ownership may move only through an explicit durable
recovery record, for example:

```text
PLANNER_REVIEW_REASSIGNMENT

notification_id: github-pr-comment:<id>
previous_receipt_comment_id: <id>
new_receipt_comment_id: <id>
reason: <explicit user recovery request or explicit prior-owner release>
```

A timeout or lack of chat response is not sufficient reason for reassignment.

The surviving Planner branch may create the reassignment record when the user
explicitly asks it to recover the already-claimed review and the branch has
verified that no authoritative Planner decision was recorded after the prior
receipt. An explicit release by the prior owning Planner is also sufficient.

After reassignment, all branches must treat the named new receipt as owner.

This recovery rule handles a lost conversation without introducing an automatic
lease/timeout that could cause two Planner branches to exercise authority.

## Existing Decision Recovery

A receiving Planner must prefer durable prior decisions over conversational
memory.

For the same exact task/head:

- an existing valid Planner final acceptance means a duplicate notification
  does not require a second final acceptance;
- an existing Planner changes-requested decision means the sender must provide a
  new material request/head before another final review;
- a merged PR means the receiving Planner performs at most a bounded
  post-merge verification when needed; it must not recreate the merge or invent
  a new in-flight state.

When provenance of an old chat session is unavailable, Planner may state that
session attribution is unknown while still independently verifying the durable
repository result.

Unknown conversation provenance alone does not invalidate scientifically valid
durable evidence.

## Sender Retry Semantics

Direct delivery is at-least-once, not exactly-once.

The sender must treat timeout/uncertain delivery as retryable and resend the
same compact envelope with the same notification ID.

The sender must not:

- create a new task/PR because delivery timed out;
- create a second durable review-request comment solely for retry;
- change exact head while claiming the old notification ID;
- interpret absence of a chat reply as rejection or approval;
- merge because a notification was sent.

If the sender later advances the PR head materially, it must create a new
durable request after the required Maintainer review and use a new notification
ID.

## Notification Triggers

Notify Planner only at meaningful Planner-actionable transitions.

Allowed default triggers:

1. `SPEC_REVIEW`
   - complete task contract is ready for independent exact-spec review;
2. `MATERIAL_DECISION`
   - Maintainer has classified a real semantic/architecture gap that cannot be
     resolved inside the approved contract;
3. `FINAL_REVIEW`
   - Maintainer final implementation/operational acceptance is recorded on the
     exact final head;
4. `NATIVE_REVIEW`
   - an accepted external native workflow requires Planner semantic/source
     review;
5. `EXCEPTION`
   - a genuine authority/landing ambiguity requires Planner action.

Do not notify Planner merely for:

- every commit;
- Implementer completion that Maintainer has not yet reviewed;
- ordinary test failures under Maintainer ownership;
- long-running job start/progress;
- routine canary/formal status;
- a request that is already resolved on the same exact head.

## Planner Verification Requirements

Receiving a valid notification authorizes Planner to **look**, not to accept.

Before any authoritative Planner decision, Planner must independently verify as
appropriate:

- current remote PR state;
- exact head and base;
- relevant task contract;
- Maintainer review/acceptance record;
- changed files/diff;
- current `main`;
- scientific/provenance evidence required by the task.

For final acceptance/landing, existing exact-head dual-acceptance rules remain
unchanged.

Immediately before merge, Planner must re-fetch PR state and exact head and use
expected-head protection when the available merge mechanism supports it.

## Relationship To Existing Implementer Coordination

T102 must integrate with
`docs/implementer_coordination.md` rather than duplicate it.

That document continues to own:

- Implementer thread IDs/cursors;
- timeout recovery;
- Implementer result receipt;
- Implementer -> Maintainer handoff.

T102 adds the next boundary:

```text
Implementer result
    -> Maintainer reads/verifies
    -> if Planner action required:
       durable Planner request comment
    -> compact direct Planner notification
    -> Planner receipt/deduplication
    -> independent Planner review
```

The Maintainer remains responsible for deciding whether an Implementer result
actually requires Planner attention.

## Required Repository Changes

Implementation must at minimum:

1. update `docs/collaboration_workflow.md` with the authoritative
   Agent -> Planner notification/authority/deduplication rules;
2. update `docs/implementer_coordination.md` so the Maintainer handoff path
   points to the new notification protocol when Planner action is required;
3. add a concise coding-agent summary to `AGENTS.md`;
4. add or update documentation navigation as needed without creating a second
   normative source;
5. provide copyable durable-request, direct-envelope, and Planner-receipt
   templates;
6. document the duplicate-Planner-branch election rule;
7. document manual-user-request compatibility.

A separate protocol document may be added if that keeps the authoritative
workflow readable. If so, `collaboration_workflow.md` must clearly state which
document owns the detailed notification mechanics and which rules remain
authoritative in the workflow.

Prefer one detailed source plus short references over duplicated normative
text.

## Optional Lightweight Tooling

Implementation may add a small helper or validation test if useful for:

- formatting a notification envelope;
- validating required fields;
- deriving/checking notification comment IDs;
- detecting duplicate Planner receipts in fixtures.

Do not build:

- a new task database;
- a background message broker;
- a new authentication service;
- a large workflow engine;
- a second PR state machine.

Documentation-only implementation is acceptable if the protocol is precise,
copyable, and operationally sufficient for Agents that already have a direct
Planner messaging mechanism.

## Required Scenarios

The landed protocol must explicitly walk through at least these scenarios:

### Scenario A — normal final review

Maintainer records exact-head final acceptance, posts one durable Planner review
request, sends one compact notification, Planner claims the request, verifies,
accepts, and merges.

### Scenario B — transport retry

Direct delivery times out. Maintainer resends the same envelope with the same
notification ID. No second GitHub review-request comment is created.

### Scenario C — duplicate Planner conversations

The same notification reaches two Planner branches. Both may attempt a receipt;
the lower GitHub receipt-comment ID becomes owner. The other branch stops
before any authoritative decision or merge.

### Scenario D — stale head

A notification names head H, but PR is now H2. Planner does not review H as
current. Sender must complete the required Maintainer review for H2 and create a
new durable notification.

### Scenario E — already resolved

A surviving Planner branch receives a notification whose exact head already has
valid Planner final acceptance or has already merged. It verifies the durable
record and does not duplicate acceptance/merge.

### Scenario F — Implementer wants Planner input

An STSRL Implementer encounters a semantic question. It reports to Main
Maintainer. Maintainer classifies the question and only then sends a Planner
notification if the issue is genuinely Planner-owned.

### Scenario G — winning Planner conversation is lost

Two Planner conversations raced and receipt A won by lower GitHub comment ID.
Conversation A is subsequently unavailable and recorded no authoritative
decision. Conversation B must not take over from silence alone. After an
explicit user recovery request or prior-owner release, B records a durable
reassignment from receipt A to its receipt and then continues the review.

## Verification

Required focused verification:

- task/document guards pass;
- all modified documentation links resolve;
- no conflict with one-task-one-PR authority;
- no wording implies that a notification itself grants approval or merge
  authority;
- no wording allows STSRL Implementer to bypass Main Maintainer by default;
- duplicate Planner branch scenario has a deterministic single-owner outcome;
- a lost winning branch can recover only through explicit durable reassignment,
  never timeout-based claim stealing;
- retries reuse the same notification ID;
- stale-head notification cannot authorize review/landing of a newer head;
- manual user review requests remain supported;
- notification mechanics have one detailed normative source rather than several
  independently maintained copies.

If helper code is added:

```bash
pytest <focused tests>
python -m compileall -q src tests
ruff check <changed Python files>
ruff format --check <changed Python files>
```

Also report the supported repository documentation/test suite outcome used for
final acceptance.

## Terminal Classification

Success terminal:

`AGENT_PLANNER_NOTIFICATION_PROTOCOL_ESTABLISHED`

Use only when:

- the role/routing boundary is explicit;
- durable-source-first request identity is defined;
- compact direct notification envelope is defined;
- retry/idempotency semantics are defined;
- duplicate Planner conversations deterministically converge to one review
  owner before authority is exercised;
- lost-owner recovery requires explicit durable reassignment rather than a
  timeout;
- notification-versus-authority separation is explicit;
- existing exact-head final acceptance and merge rules remain intact;
- Implementer/Maintainer coordination remains intact;
- required scenarios and verification pass.

No partial terminal is needed for ordinary documentation corrections. If the
protocol cannot be made internally consistent without changing existing task
authority, leave T102 `INCOMPLETE` and request Planner amendment.

## Explicit Non-Claims

T102 does not establish:

- cryptographic Agent or session identity;
- exactly-once message delivery;
- recovery of lost ChatGPT conversation history;
- proof of which historical Planner branch authored an old GitHub comment;
- automatic scientific approval;
- automatic merge authority;
- a replacement for GitHub PR evidence;
- a new scientific task;
- a change to T101's accepted terminal;
- a requirement that the user stop manually relaying messages.

## Out Of Scope

Do not perform or authorize in T102:

- simulator/native/Search/model changes;
- scientific experiments;
- task-result reinterpretation;
- GitHub account/credential redesign;
- ChatGPT/Codex product API changes;
- custom authentication infrastructure;
- a persistent message broker;
- task execution concurrency changes;
- weakening exact-head dual final acceptance.

## Execution Freedom And Material Changes

Maintainer/Implementer may choose ordinary documentation structure, template
format, helper names, and focused test organization.

Planner amendment and renewed exact-spec approval are required for any change
that would:

- give a notification authority by itself;
- allow STSRL Implementer to bypass Main Maintainer by default;
- remove durable PR anchoring;
- remove deterministic duplicate-Planner convergence;
- change one-task-one-PR or dual-final-acceptance semantics;
- grant automatic merge authority;
- require a new external service or credential.

## Acceptance And Authorization Boundary

Publishing T102 does not authorize implementation.

Before implementation, Maintainer must independently review the exact task PR
head and post:

```text
SPEC APPROVED

task: T102
approved_spec_commit: <exact full SHA>
implementation_authorized: true
```

Implementation then proceeds on the same task PR.

Final landing requires:

- Maintainer final implementation/operational acceptance;
- Planner final governance/architecture acceptance;

on the same exact final head.

T102 is governance-only. No scientific successor is authorized by its
publication or completion.
