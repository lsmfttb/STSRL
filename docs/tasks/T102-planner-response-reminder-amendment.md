# T102 Amendment: Planner Response Reminder And Stalled-Review Recovery

Artifact Eligibility Required: false

This is a normative same-ID amendment to
`T102-agent-planner-notification-protocol.md`.

It supplements the existing `WAITING_FOR_PLANNER` polling semantics when a
valid durable Planner review request has been delivered but no matching durable
Planner decision appears within the expected response interval.

It does not change task authority, review authority, routing authority, exact-
head requirements, or resume-operation semantics. The metadata-current routing
amendment and resume-operation identity amendment remain fully applicable.

## Problem Addressed

T102 previously required bounded PR polling after direct Planner delivery but
left a gap when the selected Planner conversation had received the request yet
its review execution stalled or failed to complete. Silent waiting until the
whole Maintainer wait budget expired can leave an otherwise recoverable review
stuck without another wake-up signal.

The protocol now requires bounded reminder delivery before giving up on an
unchanged, unresolved Planner request.

## Reminder Eligibility

A Planner reminder is permitted only when all of the following are true:

1. the original durable `PLANNER_REVIEW_REQUEST` still exists;
2. no valid durable Planner decision matching its `notification_id` exists;
3. the request's task, PR, phase, and exact head are still current;
4. the PR is still open and the requested action is not otherwise obsolete;
5. the current Planner route can be resolved under the metadata-current routing
   amendment; and
6. the configured reminder threshold has elapsed since the most recent
   successful direct delivery for this same durable request.

If any condition fails, do not send a reminder. Follow the existing stale-
request, routing-failure, or manual-recovery behavior instead.

## Default Reminder Timing

Unless the task or request explicitly records a longer operational expectation,
the first reminder threshold is **10 minutes** after the most recent successful
direct delivery of the unresolved request.

A task may choose a longer threshold when the expected Planner-owned action is
known to require more time, but it must not silently convert `WAITING_FOR_PLANNER`
into indefinite waiting.

For repeated reminders:

- wait at least 10 minutes after the preceding successful reminder delivery;
- send at most two reminder deliveries for one durable review request during one
  active Maintainer turn;
- continue ordinary bounded PR polling between reminders; and
- after the reminder cap or total wait budget expires, stop automatic delivery
  and use the existing manual/user-triggered recovery path.

The reminder threshold is an operational wake-up threshold, not an SLA and not
evidence that Planner should already have completed the review.

## Route Resolution Before Every Reminder

Immediately before each reminder, Main Maintainer must rerun current Planner
selection exactly as required by
`T102-route-binding-amendment.md`.

Do not reuse the thread id from the original notification merely because that
send succeeded. If the user has continued work in another current STS Planner
conversation, metadata-current selection may legitimately route the reminder to
that newer conversation.

A reminder must never widen routing to archived threads, content search,
assertion search, or an older cached endpoint.

## Reminder Message

A reminder reuses the original durable notification identity. It does not
create another PR review-request comment.

The compact direct message is:

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

`reminder_sequence` is scoped to the active Maintainer turn and the same durable
request. It is coordination metadata only.

The reminder must preserve the original task/PR/phase/exact-head/action
identity. It must not silently broaden or revise the requested action.

## Authority And Deduplication

A reminder has no approval, acceptance, merge, implementation, or scientific
authority.

Planner handling remains request-idempotent:

- re-fetch the original durable request by `notification_id`;
- independently inspect current PR/head/evidence;
- if a durable Planner decision already exists, do not duplicate the review;
- if an in-progress review can be resumed, continue that review rather than
  starting a parallel independent transaction; and
- publish only the workflow-valid durable PR decision.

Receiving one or more reminders must never cause multiple authoritative Planner
decisions for the same exact unresolved request.

## Head Or Request Drift

Before every reminder, Maintainer re-reads the PR.

If the exact head has changed materially, the old request is stale. Do not
remind against the old head. Maintainer must first perform the workflow-required
re-review and, when appropriate, create a new durable review request with a new
notification id.

If only an explicitly accepted non-material landing change preserves the prior
review authority under the governing workflow, the durable PR record must say
so before any reminder targets the new head.

## Stop Conditions

Stop reminder delivery immediately when any of the following becomes true:

- a matching durable Planner decision appears;
- the PR closes or merges;
- exact-head/request identity becomes stale;
- route resolution fails closed;
- the request is explicitly withdrawn or superseded;
- two reminders have already been delivered in the current active turn; or
- the Maintainer's total bounded wait budget expires.

A direct chat reply without the required durable PR decision does not satisfy
the completion condition.

## Relationship To Terminated Maintainer Sessions

This amendment does not claim unattended restart-safe Maintainer recovery.

If the active Maintainer turn terminates, a later user/manual-triggered
Maintainer session may inspect the durable review request and PR comments. If it
remains unresolved and current, that later session may begin a fresh bounded
wait/reminder cycle after rerunning metadata-current Planner selection.

The later session must not infer prior reminder count from chat history as
workflow authority; durable request and Planner-decision state remain the source
of truth.

## Required Operational Verification

The protocol implementation or canary coverage must demonstrate at least:

1. no reminder is sent while a matching durable Planner decision already exists;
2. first reminder occurs only after the configured threshold;
3. repeated reminders are separated by the minimum interval and capped at two
   per active turn;
4. every reminder reruns metadata-current Planner selection;
5. reminder delivery reuses the original notification id and does not create a
   new durable review request;
6. exact-head drift suppresses the reminder and forces stale-request handling;
7. a Planner decision appearing between poll cycles suppresses the next
   reminder;
8. duplicate/reminder delivery does not produce duplicate authoritative Planner
   decisions; and
9. reaching the reminder cap or total wait budget falls back to the existing
   explicit/manual recovery path rather than looping indefinitely.

## Normative Relationship

This amendment supersedes only the prior implication that bounded polling may
remain passive until the whole wait budget expires. All other T102 semantics
remain unchanged.

Before landing, keep this amendment discoverable from the T102 same-ID amendment
lookup and the concise Maintainer workflow guidance. It must not become an
unlinked hidden protocol file.
