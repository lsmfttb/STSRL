# Implementer Coordination Protocol

This guide is the operational companion to
[`collaboration_workflow.md`](collaboration_workflow.md). It governs how the
Main Maintainer delegates work to an Implementer, waits for the result, reads
that result reliably, verifies it, and continues the authorized workflow. It
does not change a task's scientific contract, approval boundary, lifecycle, or
permission scope.

## Completion invariant

A delegation is not complete merely because a thread has been started, a wait
has timed out, or the UI shows a progress update. Before returning control to
the user, the Main Maintainer must reach one of these states:

1. the Implementer has returned a readable terminal result and the Maintainer
   has independently verified it; or
2. the Implementer has reported a concrete blocker/need for input and the
   Maintainer has recorded the blocker and stopped at that boundary; or
3. a healthy, approved long-running job has been handed off through the
   repository detached-job convention with its PID, status path, logs, and ETA,
   and no immediate Maintainer action remains.

An ordinary wait timeout is not a terminal result. An empty or truncated thread
projection is not evidence that the Implementer did no work.

## 1. Prepare the handoff

Before dispatching, read the current task contract and record:

- task/PR number, exact approved contract head, base commit, and current
  lifecycle state;
- target repository, worktree, branch, and the exact input/output boundary;
- whether the work is STSRL-only, external-native, documentation-only, or a
  mixed cross-repository change;
- prohibited actions, especially simulator jobs, formal cohorts, identity
  changes, contract changes, or external mutations not authorized by the task;
- the next Maintainer action that must occur after a successful result.

The prompt must tell the Implementer to do the work, not merely investigate
unless investigation is the requested deliverable. It must require a final
receipt even when the outcome is blocked or no code change is needed. For a
cross-repository task, name the target repository explicitly; checking only the
STSRL worktree cannot establish that an external Implementer did no work.

Use the existing Implementer thread only when its current task, repository, and
context match. A materially different task or a very long/stale thread should
use a fresh context. Do not create a new user-visible task or branch silently;
obtain the required authorization and preserve the one-task/one-PR rule.

Use this compact receipt schema in the prompt:

```text
IMPLEMENTER_RESULT
state: COMPLETED | BLOCKED | FAILED
task:
repository:
worktree:
branch:
base_commit:
commit: <SHA> | none (reason)
pull_request: <URL> | none
changed_files:
verification:
artifacts_or_logs:
simulator_or_large_job_started: NO | YES (details)
contract_or_identity_change: NO | YES (details)
blocker:
next_action:
```

The Implementer may use a different prose format only if all of these facts
remain recoverable. A commit is not required for a read-only diagnosis, but
the receipt must say `commit: none` and explain why.

## 2. Dispatch and identify the turn

After sending the prompt, record the returned `threadId` and `hostId`. Treat
these as the control-plane identity of the delegation. Capture the first
`wait_threads` cursor and use it for later waits. Do not dispatch a duplicate
Implementer because a first wait timed out.

For a task with an external native lane, the handoff must also require:

- an isolated native worktree and temporary branch from the verified native
  base;
- the exact native commit and PR/compare link in the receipt;
- a statement of native semantic risk and the required independent review;
- no change to the STSRL pinned identity until the native result is accepted
  and the task contract permits the identity update.

## 3. Wait without prematurely ending the task

`wait_threads` is the state/wakeup mechanism. Use it as follows:

1. Wait with a bounded interval (normally 30--60 seconds) for the target
   thread.
2. If the result is a timeout and the thread is still `active`, continue the
   same delegation with the returned cursor. A timeout is not permission to
   send another prompt or return a final status.
3. Back off rather than polling unchanged state continuously. Do not narrate
   every unchanged snapshot.
4. If the thread needs attention, read the request and handle it before
   returning to the user.
5. If the thread completes, immediately enter the read-and-verify phase below;
   do not end the Maintainer turn just because the Implementer turn ended.

Commentary sent by the Maintainer does not wake a `wait_threads` wait. A
commentary update may explain that work is still active, but it is not a
substitute for continuing the bounded wait or inspecting the target state.

For long-running work, distinguish the Implementer turn from a child simulator
job. A job may be handed off only when it was authorized and launched through
the detached-job convention; record its PID/status/log paths once and monitor
the status artifact. Never start a duplicate job because the Implementer has
not yet posted a final message.

## 4. Read the result using the correct channel

Use the strongest available read path in this order:

1. If the App Server low-level methods are available, read the exact completed
   turn with `thread/turns/list` and `itemsView: "full"`, or use
   `thread/items/list` scoped to that `turnId`.
2. Otherwise use `read_thread` with `includeOutputs: true`, a small enough
   `maxOutputCharsPerItem`, and the correct page cursor; page through older
   turns when the response is truncated.
3. If the UI labels content as coming “from another task”, identify the source
   child/parent thread before interpreting the content. Do not assume that a
   forwarded result is stored as an ordinary item in the thread being read.
4. Independently inspect the target repository/worktree, remote PR/commit,
   artifact manifest, and relevant test/log status. For a native task, inspect
   the native repository as well as the STSRL repository.

The high-level `read_thread` projection may contain turn metadata without all
forwarded, compacted, or delegated items. Therefore all of the following mean
`READ_UNCERTAIN`, not “no result”:

- `items: []` on a completed turn;
- `latestAssistantMessageId: null`;
- `latestToolMarkerId: null`;
- a `completed` turn with no visible message in the returned page;
- a wait timeout while the thread is still active.

Never report “Implementer did nothing” from one of those observations. First
check the durable target state. A real commit/PR/test artifact is sufficient to
reconstruct the result even if the message projection failed; record the
communication discrepancy for later troubleshooting.

## 5. Recovery when the message is unreadable

Use this bounded recovery sequence, once per delegation:

1. Confirm the target thread reached `completed`, `needs attention`, or an
   actual error; do not treat a timeout as completion.
2. Read the exact turn again through the best available route, using the
   returned cursor or turn ID.
3. Inspect the target repository and remote PR/commit before sending another
   prompt.
4. If no durable result is found and the thread is idle, send one short,
   status-only prompt. It must prohibit code changes, simulator jobs, and
   broad tests; it asks only for the receipt schema and the concrete blocker.
5. Wait for that turn to reach a terminal state and read it again.
6. If it is still unreadable, classify the situation as a communication/read
   failure. Do not claim failure, do not launch the experiment, and do not
   repeatedly resend prompts. Ask for a fresh authorized implementer context or
   user direction if no safe in-scope recovery remains.

If a durable commit or PR is found at any point, reconstruct the Implementer
receipt from that evidence and continue the Maintainer review. A missing final
message does not invalidate verified work.

## 6. Continue after a valid result

The Implementer's completion is a handoff point, not the end of the
Maintainer's task. In the same workflow, the Main Maintainer must:

1. inspect the exact diff, target branch, worktree cleanliness, and provenance;
2. verify the reported tests, artifacts, hashes, and relevant contract gates;
3. classify scope, scientific, information-regime, native-lineage, and
   documentation impact independently;
4. apply the next authorized action: update the task PR, request Planner
   review, run the next approved stage, or record the precise blocker;
5. if another Implementer turn is genuinely required, send it only after this
   review and carry its new thread/cursor separately;
6. return a final user update only after no immediate authorized Maintainer
   action remains.

Do not return to the user with only “Implementer finished” when the receipt
contains a commit, PR, artifact, test result, or explicit next step that the
Maintainer can safely process. Conversely, do not continue into a scientific
stage when the result changes a pinned identity or exposes a contract gap that
requires Planner approval.

## State model

```text
DISPATCHED -> ACTIVE -> TURN_COMPLETED -> READ -> VERIFIED -> CONTINUE -> HANDOFF
                  |                       |
                  |                       +-> READ_UNCERTAIN -> durable-state check
                  |                                           -> one status retry
                  |                                           -> VERIFIED or BLOCKED
                  +-> TIMEOUT (remain ACTIVE; no duplicate launch)
```

`BLOCKED` means a concrete external, contract, permission, or user-input
boundary remains after the safe recovery sequence. It does not mean that a
wait call returned a timeout or that a response projection was incomplete.

## Minimal handoff template

```text
You are the Implementer for <task/PR>. Work only in <repository> at
<worktree>/<branch>, based on <exact base commit>.

Objective: <one concrete deliverable>.
Do not: <unapproved experiments, identity changes, contract changes, or
large jobs>.
Required checks: <task-specific checks>.

Do not stop after planning. When finished, return IMPLEMENTER_RESULT with the
exact branch, commit/PR, changed files, checks, artifacts/logs, simulator/job
status, contract impact, blocker, and next action. If blocked, return the same
receipt with state=BLOCKED and the concrete boundary.
```

This protocol is intentionally operational. Scientific meaning remains owned
by the approved task contract, Planner review, and the repository's existing
native-lineage and acceptance documents.
