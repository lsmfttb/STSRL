# T102 Amendment: Planner Review Reminder And Workflow Continuation Recovery

Artifact Eligibility Required: false

This is a normative same-ID amendment to
`T102-agent-planner-notification-protocol.md`.

It closes two distinct recovery gaps in the T102 Planner-request path:

1. a valid durable Planner review request has been delivered, but no matching
   durable Planner decision appears within the expected response interval; and
2. a matching durable Planner decision exists, but that decision leaves an
   immediate Planner-owned continuation unfinished, such as final landing after
   exact-head dual acceptance.

It does not change task authority, review authority, merge authority, routing
identity, exact-head requirements, or the scientific meaning of any task. The
metadata-current routing amendment and resume-operation identity amendment
remain fully applicable.

## Problem Addressed

T102 previously required bounded PR polling after direct Planner delivery but
left two ways for an otherwise recoverable workflow to stall:

- **pre-decision stall:** the selected Planner conversation received a request,
  but review execution did not produce a durable decision; and
- **post-decision stall:** Planner recorded a durable decision, but stopped
  before completing the next action that the governing workflow still assigned
  to Planner.

A durable `PASS` is therefore not automatically the end of the Planner turn.
The end of the Planner-owned portion of the workflow is determined by durable
handoff/completion state, not merely by the existence of a decision comment.

This amendment adds bounded reminders for both stages and an explicit
post-decision continuation contract.

## Derived Request State

T102 does not create a new lifecycle registry. The following states are derived
from the existing PR request, Planner decision, and continuation evidence:

- `WAITING_FOR_PLANNER_DECISION`: the durable request is current and unresolved;
- `WAITING_FOR_PLANNER_CONTINUATION`: a matching durable Planner decision exists
  and says the immediate next action is still Planner-owned;
- `HANDOFF_READY`: the matching durable Planner decision assigns the immediate
  next action to Maintainer or says no further Planner action is required;
- `PLANNER_CONTINUATION_COMPLETED`: the Planner-owned continuation has durable
  completion evidence; and
- `PLANNER_CONTINUATION_BLOCKED`: Planner durably records why the owned
  continuation cannot safely complete and who must act next.

These names are explanatory state labels only. The durable PR evidence remains
the authority.

## Durable Planner Decision Continuation Fields

For every future T102-triggered durable Planner decision, Planner must include:

```text
continuation_owner: PLANNER | MAINTAINER | NONE
continuation_action_kind: <stable action kind or NONE>
continuation_action_key: <stable action key or NONE>
```

`continuation_action_kind` and `continuation_action_key` use the same grammars
and stable-identity expectations as the T102 resume-operation identity
amendment.

Rules:

- `continuation_owner: PLANNER` means the current Planner turn is **not done**.
  Planner must immediately continue the named action until it is durably
  completed or durably blocked.
- `continuation_owner: MAINTAINER` is an explicit handoff. Maintainer may stop
  waiting for Planner continuation and resume the governing workflow.
- `continuation_owner: NONE` means the decision itself is the terminal Planner
  action for this request.
- `PLANNER` requires a non-`NONE` action kind and action key.
- `MAINTAINER` or `NONE` may use `NONE` for both action fields when no stable
  Planner continuation identity is needed.

These fields describe **who owns the immediate continuation**, not who owns the
whole task. They do not grant authority that the governing workflow does not
already provide.

If a workflow-valid Planner decision omits these fields after this amendment is
landed, automatic post-decision continuation recovery fails closed and requires
manual correction. Maintainer must not guess ownership from prose.

## Required Final-Review Landing Semantics

The repository workflow already assigns task landing to Planner after both final
acceptances exist on the same exact final head.

Therefore, when Planner records a final scientific/architecture `PASS` and all
of the following are true:

1. Maintainer final implementation/operational acceptance exists for the same
   exact head;
2. Planner final acceptance is being recorded for that same exact head; and
3. no governing rule requires another role to act before landing,

that Planner decision must use:

```text
continuation_owner: PLANNER
continuation_action_kind: MERGE_PR
continuation_action_key: <repository>#<pr>@<exact-head>
```

After recording the decision, Planner must not return merely because the `PASS`
comment exists. In the same workflow it must:

1. refresh PR/head/base/current-main state;
2. verify exact-head dual acceptance still holds;
3. perform the required pre-landing race/mergeability checks;
4. merge using the exact expected head when still authorized;
5. verify the resulting `main` state; and
6. record durable continuation completion.

If any precondition fails, Planner must not merge. It records durable
`PLANNER_CONTINUATION_BLOCKED` instead.

This requirement does not weaken fail-closed merge discipline. It removes the
incorrect stopping point between final `PASS` and a still-Planner-owned landing.

## Planner Continuation Completion Record

After a Planner-owned continuation completes, Planner records:

```text
PLANNER_CONTINUATION_COMPLETE
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<original-request-comment-id>
planner_decision_comment_id: <decision-comment-id>
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
decision_exact_head: <sha>
continuation_action_kind: <kind>
continuation_action_key: <key>
status: COMPLETED
completion_evidence: <durable evidence/predicate>
```

For `MERGE_PR`, completion evidence must identify the merged PR/result and the
verified post-merge `main` identity. The accepted decision head remains
`decision_exact_head`; the resulting merge commit may of course be a different
commit.

The completion record does not create merge authority. It records that an
already-authorized Planner continuation actually completed.

A workflow-specific durable completion record such as a landing-complete record
may satisfy this requirement only if it contains equivalent correlation fields
and durable completion evidence.

## Planner Continuation Blocked Record

If Planner owns the continuation but cannot safely finish it, Planner records:

```text
PLANNER_CONTINUATION_BLOCKED
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<original-request-comment-id>
planner_decision_comment_id: <decision-comment-id>
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
decision_exact_head: <sha>
continuation_action_kind: <kind>
continuation_action_key: <key>
status: BLOCKED
blocker: <concise durable blocker>
next_owner: MAINTAINER | USER
```

Examples include head drift after acceptance, loss of same-head dual acceptance,
main/base race, mergeability failure, or unavailable required repository state.
The blocker record ends automatic Planner continuation for that turn and makes
handoff explicit. It must not disguise an ordinary transient omission as a
workflow blocker.

## Pre-Decision Reminder Eligibility

A `PLANNER_REVIEW_REMINDER` is permitted only when all of the following are true:

1. the original durable `PLANNER_REVIEW_REQUEST` still exists;
2. no valid durable Planner decision matching its `notification_id` exists;
3. the request's task, PR, phase, and exact head are still current;
4. the PR is still open and the requested action is not otherwise obsolete;
5. the current Planner route can be resolved under the metadata-current routing
   amendment; and
6. the configured reminder threshold has elapsed since the most recent
   successful direct delivery for this same durable request.

If any condition fails, do not send a review reminder. Follow the existing
stale-request, routing-failure, or manual-recovery behavior instead.

## Post-Decision Continuation Reminder Eligibility

A `PLANNER_CONTINUATION_REMINDER` is permitted only when all of the following are
true:

1. a matching durable Planner decision exists;
2. that decision has `continuation_owner: PLANNER`;
3. neither a valid matching continuation-complete record nor a matching
   continuation-blocked record exists;
4. the continuation action identity still matches the durable decision;
5. the governing workflow has not made the action obsolete;
6. the current Planner route can be resolved under the metadata-current routing
   amendment; and
7. the configured continuation reminder threshold has elapsed since Maintainer
   first observed the unresolved Planner-owned continuation or since the most
   recent successful continuation reminder, whichever is later.

Before sending, Maintainer must also inspect the durable completion predicate
when it is cheaply observable. If the action already completed but only the
completion record is missing, the reminder asks Planner to reconcile durable
state and write the missing completion record; it must not cause the action to
be replayed.

## Default Reminder Timing

Unless the task or request explicitly records a longer operational expectation,
both the first review-reminder threshold and the first continuation-reminder
threshold are **10 minutes**.

A task may choose a longer threshold when the expected Planner-owned work is
known to require more time, but it must not silently convert either waiting
stage into indefinite waiting.

For each waiting stage independently:

- wait at least 10 minutes after the preceding successful reminder delivery;
- send at most two reminder deliveries during one active Maintainer turn;
- continue ordinary bounded PR polling between reminders; and
- after the reminder cap or total wait budget expires, stop automatic delivery
  and use the existing manual/user-triggered recovery path.

The thresholds are operational wake-up thresholds, not SLAs and not evidence
that Planner should already have finished the work.

## Route Resolution Before Every Reminder

Immediately before every review or continuation reminder, Main Maintainer reruns
current Planner selection exactly as required by
`T102-route-binding-amendment.md`.

Do not reuse the thread id from the original notification, decision, or earlier
reminder merely because a previous send succeeded. If the user has continued
work in another current STS Planner conversation, metadata-current selection may
legitimately route the reminder to that newer conversation.

A reminder must never widen routing to archived threads, content search,
assertion search, or an older cached endpoint.

## Review Reminder Message

A pre-decision reminder reuses the original durable notification identity. It
does not create another PR review-request comment.

```text
PLANNER_REVIEW_REMINDER
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<original-request-comment-id>
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
phase: <phase>
exact_head: <sha>
reminder_sequence: <1 or 2>
requested_action: <same concise Planner-owned action>
evidence_anchor: github-pr-comment:<original-request-comment-id>
reason: no_matching_durable_planner_decision_after_expected_wait
authority: reminder_only
```

The reminder preserves the original task/PR/phase/exact-head/action identity. It
must not silently broaden or revise the requested action.

## Continuation Reminder Message

A post-decision reminder also reuses the original notification identity and
binds the durable Planner decision/action identity:

```text
PLANNER_CONTINUATION_REMINDER
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<original-request-comment-id>
planner_decision_comment_id: <decision-comment-id>
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
decision_exact_head: <sha>
continuation_action_kind: <kind>
continuation_action_key: <key>
reminder_sequence: <1 or 2>
reason: planner_owned_continuation_has_no_completion_or_blocker
authority: reminder_only
```

This is not a new review request and does not ask Planner to reconsider the
scientific/architecture decision unless current durable state independently
invalidates that decision under the governing workflow.

## Planner Handling And Deduplication

All reminders are coordination-only and carry no approval, acceptance, merge,
implementation, or scientific authority.

On a review reminder, Planner:

- re-fetches the original durable request by `notification_id`;
- independently inspects current PR/head/evidence;
- does not duplicate an already-existing durable decision; and
- resumes the same review transaction rather than starting a parallel review.

On a continuation reminder, Planner:

- fetches and validates the referenced durable decision;
- checks completion evidence before retrying the action;
- if already complete, does not replay and writes/reconciles the completion
  record when needed;
- if incomplete and still authorized, resumes the exact same continuation
  action; and
- if no longer safely executable, writes a continuation-blocked record instead
  of silently stopping.

Duplicate reminders must never produce duplicate authoritative decisions or
unsafe duplicate non-idempotent actions.

## Head Or Request Drift

Before every reminder, Maintainer re-reads the PR.

Before a durable Planner decision, material exact-head drift makes the original
request stale. Do not remind against the old head; follow the workflow-required
re-review/new-request path.

After a durable decision, head/base/main drift is evaluated against the specific
continuation action. Maintainer must not invent preserved authority. For a
Planner-owned merge continuation, any loss of exact-head dual acceptance or
pre-landing race safety requires Planner to re-evaluate and normally record a
continuation blocker rather than merge.

An explicitly accepted non-material landing-only change preserves authority only
when the governing workflow's required role records say so.

## Maintainer Polling State Machine

After direct delivery, Maintainer remains in bounded polling and evaluates
states in this order:

1. **No matching durable Planner decision:** remain
   `WAITING_FOR_PLANNER_DECISION`; issue bounded review reminders when eligible.
2. **Decision says `continuation_owner: MAINTAINER`:** stop Planner waiting and
   resume the Maintainer-owned workflow.
3. **Decision says `continuation_owner: NONE`:** stop Planner waiting; the
   Planner-owned part of this request is complete.
4. **Decision says `continuation_owner: PLANNER`:** remain
   `WAITING_FOR_PLANNER_CONTINUATION`; do not treat the decision itself as
   completion.
5. **Matching continuation completion appears:** validate evidence, then resume
   from the completed durable state.
6. **Matching continuation blocker appears:** stop automatic Planner waiting and
   follow the recorded handoff/blocker.

This ordering is the core fix for the post-decision stall class.

## Stop Conditions

Stop review reminders immediately when a matching durable Planner decision
appears or the request becomes stale/closed/obsolete.

Stop continuation reminders immediately when:

- matching durable completion appears;
- matching durable blocker appears;
- the action becomes obsolete;
- route resolution fails closed;
- two continuation reminders have already been delivered in the active turn; or
- the Maintainer's total bounded wait budget expires.

A direct chat reply alone never satisfies a durable decision, completion, or
blocker condition.

## Relationship To Terminated Maintainer Sessions

This amendment does not claim unattended restart-safe Maintainer recovery.

If the active Maintainer turn terminates, a later user/manual-triggered
Maintainer session may reconstruct the derived state from durable request,
decision, completion, and blocker evidence. If work remains current and
unresolved, that later session may begin a fresh bounded reminder cycle after
rerunning metadata-current Planner selection.

The later session must not infer prior reminder count or completion from chat
history. Durable PR/repository state remains authoritative.

## Required Repository Changes

Implementation of this amendment must at minimum:

1. keep this file as the normative same-ID recovery/continuation amendment;
2. add it to the T102 same-ID amendment lookup in `docs/tasks/ARCHIVE.md`;
3. update `docs/collaboration_workflow.md` so Maintainer distinguishes waiting
   for a decision from waiting for a Planner-owned continuation, and so Planner
   final `PASS` does not terminate a still-Planner-owned landing path;
4. update `docs/implementer_coordination.md` so Maintainer does not return to the
   user or dispatch new Implementer work while a required Planner continuation
   remains unresolved;
5. add a concise `AGENTS.md` reminder covering both reminder stages and the
   Planner post-decision continuation obligation; and
6. preserve metadata-current routing, exact-head authority, and existing
   resume-operation semantics without duplicating the full T102 mechanics.

A helper/test module is optional. No scientific experiment, native change, T107
rewrite, controller change, or simulator execution is authorized by this task.

## Required Verification

Documentation/task guards must pass. In addition, implementation/tests or a
bounded protocol canary must demonstrate at least:

1. no review reminder is sent while a matching durable Planner decision exists;
2. first review reminder occurs only after the configured threshold;
3. repeated review reminders obey minimum spacing and the two-reminder cap;
4. every reminder reruns metadata-current Planner selection;
5. review reminders reuse the original notification id and create no new durable
   review request;
6. exact-head drift before decision suppresses review reminders and triggers
   stale-request handling;
7. every future T102-triggered Planner decision has valid continuation fields;
8. `continuation_owner: MAINTAINER` and `NONE` end Planner waiting without a
   continuation reminder;
9. `continuation_owner: PLANNER` keeps Maintainer in bounded waiting until a
   matching completion or blocker appears;
10. a continuation reminder binds the original notification, decision comment,
    exact decision head, action kind, and action key;
11. already-completed continuation with a missing completion record is reconciled
    without replaying the action;
12. duplicate/reminder delivery does not duplicate a Planner decision or unsafe
    continuation action;
13. final-review same-head dual acceptance is represented as Planner-owned
    `MERGE_PR` continuation and reaches either verified landing completion or a
    durable blocker; and
14. reaching either reminder cap or total wait budget falls back to explicit
    manual recovery rather than looping indefinitely.

A fixture/test may model final landing without merging a live scientific PR. A
live canary, if used, must be non-authoritative and must not create scientific or
merge authority.

## Normative Relationship

This amendment supersedes only the prior implication that:

- bounded `WAITING_FOR_PLANNER` polling may remain passive until the whole wait
  budget expires; or
- the appearance of any durable Planner decision necessarily ends the
  Planner-owned workflow.

All other T102 semantics remain unchanged.

Before final landing, keep this amendment discoverable from the T102 same-ID
amendment lookup and concise workflow guidance. It must not become an unlinked
hidden protocol file.
