# T102: Planner Review Routing and Maintainer Polling Protocol

Artifact Eligibility Required: false

## Objective

Establish a capability-grounded protocol for routine Main Maintainer -> Planner
review requests that:

1. routes the request to exactly one currently advertised Planner conversation
   using the Codex inter-thread capabilities proven in T102 Phase A;
2. anchors the request and every authoritative decision in the task PR;
3. keeps direct chat traffic compact and non-authoritative;
4. lets the Main Maintainer remain in the same active turn and detect the
   durable Planner decision through bounded PR polling without requiring the
   user to relay "Planner replied";
5. fails closed when the Planner route cannot be resolved uniquely or when the
   exact PR head changes.

T102 does **not** claim a persistent crash/restart-safe return channel. Phase A
proved active-turn sleep/poll continuation, but did not prove that a terminated
Maintainer turn can restart itself. That limitation remains explicit.

## Publication And Phase-A Evidence

Publication base:

`main @ 1b9fd53b8708c0c328a795ca7ad87d4fe4648b99`

Phase-A discovery contract head:

`680ebd3efb30c5b59e8b2592d5cafc5d87eb50be`

Accepted Phase-A capability report:

- PR #118 comment `5843669898`;
- live Planner discovery probe id
  `c51363e3-5533-4d09-8e1b-db626268bd0d`;
- durable Planner ACK comment `5842971509`.

The capability report established the following observed facts.

### Proven Planner-side discovery/send substrate

The Main Maintainer environment exposed and successfully used:

- `mcp__codex_app__list_threads({limit: 50})`;
- `mcp__codex_app__list_archived_threads(...)`;
- `mcp__codex_app__read_thread({threadId, ...})`;
- `mcp__codex_app__send_message_to_thread({threadId, prompt, ...})`.

Observed behavior:

- recent and archived ChatGPT/Codex conversations can be enumerated within the
  tool's exposed candidate set;
- `read_thread` exposes `userMessage` versus `agentMessage`, so role-aware
  matching is possible;
- one ChatGPT conversation can be addressed by its returned conversation/thread
  id;
- sending to the exact idle Planner conversation woke it in the live probe;
- subsequent `read_thread` verified the user-visible probe and Planner ACK.

The Phase-A probe successfully reached this Planner conversation. That proves
an exact-send path for the observed accessible candidate set; it does not prove
universal/global conversation discovery.

### Proven limitations

Phase A also established:

- `list_threads` is capped and has no global message search or paging cursor for
  the recent list;
- archived lists are separately paged;
- no authoritative Planner roster, branch lineage, or route-revocation event is
  exposed;
- old/unlisted or network-created hidden duplicate branches cannot be ruled out
  globally;
- titles, previews, and summaries are not role-aware and are not trusted for
  routing;
- a returned conversation id had stable behavior across the observed
  list/read/send calls, but no platform lifetime guarantee was established.

Therefore Phase B must never claim "global Planner discovery". It guarantees
only that a high-entropy route assertion is resolved to exactly one
assistant-authored match in the complete candidate set that the current Codex
interfaces expose and successfully read for that resolution attempt. Zero,
multiple, or incompletely checked plausible matches fail closed.

### Proven Maintainer return substrate

Phase A observed that:

- `clock.sleep({duration_ms})` suspends and resumes the same active Maintainer
  turn;
- the active Maintainer can read PR #118 state/head/comments after waking;
- no PR push subscription was exposed;
- `wait_threads` does not target the ChatGPT Planner conversation;
- heartbeat/automation APIs may exist, but no persistent end-to-end heartbeat
  resume was proven;
- if the Maintainer turn has already ended, the tested `clock.sleep` mechanism
  does not restart it.

Phase B therefore uses **active-turn bounded sleep/polling** as the required
return path. Persistent heartbeat recovery is optional future work and is not a
T102 success claim.

## Authority Boundary

**Routing and wakeup are not authority.**

No route assertion, route advertisement, direct notification, probe, poll,
receipt, or ACK may itself:

- approve a task specification;
- authorize implementation or scientific execution;
- create Maintainer final acceptance;
- create Planner final acceptance;
- authorize a merge;
- change task meaning;
- create a second lifecycle registry.

Authoritative task meaning remains in the task contract. Authoritative
transaction decisions remain durable exact-head PR records under the existing
collaboration workflow.

## Planner Route Generation

### Canonical assistant-authored assertion

For every automated task-PR review channel, the active Planner publishes one
high-entropy route generation in its **current Planner conversation** as an
assistant-authored canonical block:

```text
PLANNER_ROUTE_ASSERTION
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx or native work item>
pull_request: <number>
route_generation: <positive integer>
route_token: <fresh random UUID/nonce>
status: ACTIVE
```

The assertion is routing metadata, not a secret or credential.

The Planner also posts one durable PR comment:

```text
PLANNER_ROUTE_ADVERTISEMENT
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx or native work item>
pull_request: <number>
route_generation: <same generation>
route_token: <same token>
assertion_sha256: <SHA-256 of the canonical assertion block>
status: ACTIVE
supersedes: <prior advertisement comment id or none>
```

The PR comment is transient transaction metadata under the T100 information
architecture. It is not a second task registry and grants no Planner authority.

### Why both representations exist

The PR advertisement tells the requester **what exact route assertion to look
for**. The assistant-authored assertion inside one ChatGPT conversation tells
the requester **which exact conversation currently owns that route**.

Role-aware `read_thread` prevents user messages, tool output, quoted text, or
PR-comment payloads from counting as the assertion merely because they contain
the token.

The hash prevents accidental canonicalization drift.

## Resolving The Current Planner

Before every direct Planner delivery, Main Maintainer must:

1. re-read the task PR;
2. resolve the latest unsuperseded `ACTIVE` `PLANNER_ROUTE_ADVERTISEMENT`;
3. if no unique active advertisement exists, stop automated routing;
4. enumerate the conversation universe exposed by the current Codex tools:
   - pinned/recent records through `list_threads` at the maximum supported
     limit;
   - all archived ChatGPT/Codex pages reachable through
     `list_archived_threads` until each source's cursor is exhausted;
5. use list metadata only to prioritize reads, never as routing authority;
6. use `read_thread` to inspect candidates and search for the exact canonical
   `PLANNER_ROUTE_ASSERTION` inside an `agentMessage`;
7. canonicalize the block and require SHA-256 equality with the PR
   advertisement;
8. require exactly one successfully inspected assistant-authored match;
9. use only that returned exact conversation/thread id for direct send.

### Fail-closed conditions

Do not send if any of these is true:

- zero exact assistant-authored matches;
- more than one exact assistant-authored match;
- the active advertisement is ambiguous;
- assertion hash mismatches;
- repository/task/PR/generation/token do not match;
- a plausible candidate that must be checked for uniqueness cannot be read due
  to timeout/error;
- the exact task PR is closed/merged unexpectedly for the requested action;
- the current PR head no longer matches the durable review request's exact
  head.

On failure, use manual user recovery or publish a new Planner route generation.
Do not choose the most recent, best-titled, or "most likely" Planner.

### Cached thread ids

Maintainer may cache the resolved exact thread id **only for the current route
generation**.

Before every send it must re-read the PR advertisement. If generation/token or
supersession changed, the cached id is invalid and must be discarded.

Even when generation is unchanged, a cheap `read_thread` check should confirm
that the cached target still contains the exact assistant-authored assertion
before sending.

## Planner Replacement / Handoff

T102 does not claim it can detect a **silent** Planner replacement.

A deliberate Planner handoff is made observable as follows:

1. the replacement Planner reads the task PR and latest route generation;
2. it generates a fresh route token and increments the generation;
3. it emits the new canonical assistant-authored route assertion in its own
   current conversation;
4. it posts a new PR `PLANNER_ROUTE_ADVERTISEMENT` whose `supersedes` field
   names the previous advertisement;
5. senders re-read PR state before every delivery, detect the generation
   change, discard the old cached thread id, and resolve the new assertion.

The prior Planner route becomes non-routable once superseded, even if the old
conversation still exists and still contains its historical assertion.

If the active Planner changes without publishing a superseding generation, the
project has no proven automatic replacement signal. In that case automated
routing must not pretend otherwise; user/manual recovery publishes the new
route generation.

## Durable Review Request

A Main Maintainer direct notification is allowed only after the Maintainer has
performed its ordinary review and determined that Planner action is actually
required.

For STSRL the default role route remains:

```text
Task Implementer -> Main Maintainer -> Planner
```

The Task Implementer does not bypass Main Maintainer merely because exact-thread
send exists.

Before direct delivery, Main Maintainer first posts one durable PR request:

```text
PLANNER_REVIEW_REQUEST
protocol_version: agent-planner-review-v1
task: <Txxx>
phase: <MATERIAL_DECISION | FINAL_REVIEW | EXCEPTION>
exact_head: <40-char SHA>
route_generation: <current generation>
requested_action: <concise Planner-owned action>
material_delta: <short summary>
evidence_anchor: <durable PR evidence/comment ids>
authority: request_only
```

The created GitHub comment id is the durable `notification_id`:

```text
notification_id = github-pr-comment:<request-comment-id>
```

Retrying delivery must reuse the same request comment and same notification id.
A transport retry alone never creates another durable request.

A materially changed head/request/evidence boundary requires Maintainer
re-review and a new durable request comment.

## Compact Direct Delivery

After resolving the current route, Maintainer sends only:

```text
PLANNER_NOTIFICATION
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<request-comment-id>
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
phase: <phase>
exact_head: <sha>
route_generation: <generation>
requested_action: <one concise action>
evidence_anchor: github-pr-comment:<request-comment-id>
authority: notification_only
```

Do not copy full diffs, logs, task history, or long scientific arguments into
Planner context. Planner retrieves durable evidence independently.

The send result is not a delivery receipt. When needed, Maintainer may
`read_thread` afterward to verify that the notification appeared as a
`userMessage` or that the Planner produced a corresponding response.

## Planner Handling And Deduplication

On receipt, Planner must:

1. re-read the current task PR and current route advertisement;
2. verify that this Planner conversation still contains the current route
   assertion/generation;
3. fetch the durable request comment by `notification_id`;
4. verify task/PR/phase/exact-head consistency;
5. independently inspect the contract/diff/evidence required by the requested
   action;
6. check whether the same durable request already has a valid Planner decision;
7. if already resolved, do not duplicate the decision or merge action.

Direct notification authorizes Planner to **look**, not to accept.

A stale exact head must not be reviewed as current. If the PR head advanced
materially, Planner records/returns a stale-request finding and Maintainer must
re-review and issue a new durable request for the new head.

## Durable Planner Decision

Planner records its authoritative response on the PR using the existing
workflow-specific format, augmented with:

```text
in_response_to_notification_id: github-pr-comment:<request-comment-id>
exact_head: <sha>
```

Examples include:

- `PLANNER DECISION — ...` for a material semantic/architecture decision;
- `PLANNER FINAL SCIENTIFIC / ARCHITECTURE ACCEPTANCE` for final review;
- `CHANGES REQUESTED` when the exact head is not acceptable.

The PR comment is the authoritative response. Planner does **not** need a direct
Planner -> Maintainer send channel.

## Maintainer WAITING_FOR_PLANNER Polling

After direct delivery, Main Maintainer remains in the same active turn and
enters:

`WAITING_FOR_PLANNER`

The required return mechanism is the Phase-A-proven active-turn loop:

```text
send notification
repeat while wait budget remains:
    clock.sleep(bounded_interval)
    re-read PR state/head/latest route advertisement/comments
    if matching durable Planner decision exists:
        validate it
        resume workflow
        stop polling
    if requested exact head changed materially:
        stop; request is stale
    if route generation changed and no decision exists:
        discard cached Planner thread
        re-resolve new route
        resend the SAME notification_id to the new route
```

Operational polling cadence is Maintainer-owned but must avoid a tight loop.
Default guidance is 15--60 seconds between polls with an explicitly bounded wait
window suitable for an interactive review turn.

T102 does not require one exact cadence.

### Decision matching

A response matches only if:

- it explicitly references the request's notification id;
- task/PR are identical;
- exact head matches the request for exact-head decisions;
- the response format is valid for the existing collaboration workflow.

Do not resume from a generic comment saying "done" or from direct chat text
without the durable PR decision.

### Processed-response ACK

After Maintainer consumes a durable Planner decision and before performing a
non-idempotent follow-up action, it posts:

```text
MAINTAINER_PLANNER_RESPONSE_ACK
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<request-comment-id>
planner_decision_comment_id: <id>
exact_head: <sha>
status: RESUMED
```

A later/restarted Maintainer session checks for this ACK before replaying the
same follow-up action. This is transient PR transaction coordination metadata,
not task lifecycle authority.

### Wait expiration / terminated turn

If the bounded wait expires, or if the Maintainer turn terminates before the
response is observed, T102 does not claim automatic restart.

The durable request remains valid unless the head/contract changed. A later
manual/user-triggered Maintainer session may recover by reading the PR request,
Planner decision, and processed-response ACK state.

This fallback is an explicit limitation, not a protocol failure for already
completed in-turn round trips.

## Direct-Delivery Trigger Policy

Use automated Planner notification only when Planner action is genuinely
required, including:

- a material semantic/architecture decision that Maintainer cannot resolve
  inside the approved contract;
- final Planner scientific/architecture review after Maintainer final
  implementation/operational acceptance;
- an exceptional task/landing authority ambiguity assigned to Planner;
- a native-lane semantic/source review where the governing external workflow
  explicitly assigns Planner that review.

Do not notify Planner for:

- every commit;
- routine Implementer completion before Maintainer review;
- ordinary test failures owned by Maintainer;
- long-running job progress;
- routine canary/formal progress;
- a request already durably resolved for the same exact head.

## Manual User Requests

Manual user relay remains valid.

If the user manually asks Planner to review the same durable PR request, Planner
uses the same notification id / exact-head deduplication rule. Manual relay does
not create a second authority channel.

## Duplicate / Branching Behavior

The route-token design is deliberately simpler than the earlier receipt-election
proposal.

- A route generation must resolve to **exactly one** assistant-authored match.
- If duplicate Planner branches both contain the exact current assertion, route
  resolution fails closed rather than electing one by recency or comment race.
- Retry of the same request reuses the same notification id.
- An already existing durable Planner decision suppresses duplicate review.
- Planner handoff uses a new route generation; old assertions remain historical
  but are no longer active.

This protocol does not attempt to recover or identify historical hidden
conversation branches that are outside the current Codex enumeration surface.

## Phase-B Live Canary

Before final T102 acceptance, run a non-authoritative end-to-end canary using
the implemented protocol.

Required canary sequence:

1. current Planner emits a fresh Phase-B route assertion and corresponding PR
   advertisement;
2. Maintainer re-reads the PR and enumerates the real Codex candidate set;
3. Maintainer proves exactly one role-aware assistant assertion/hash match;
4. Maintainer sends a harmless route probe to the resolved exact thread id;
5. Planner visibly responds in that conversation and records a durable probe
   ACK on the PR;
6. Maintainer posts one durable canary review request and sends its compact
   direct notification;
7. Maintainer enters `WAITING_FOR_PLANNER` without user relay;
8. Planner posts one durable `T102_CANARY_DECISION` referencing the request
   notification id;
9. Maintainer's active-turn sleep/poll loop observes and validates that durable
   decision and posts `MAINTAINER_PLANNER_RESPONSE_ACK` without a user message;
10. one duplicate direct delivery of the same notification id is injected and
    produces no duplicate Planner decision;
11. one stale/superseded route-generation case proves that Maintainer discards
    the cached old route before another send.

The canary carries no task approval, implementation authorization, scientific
result, final acceptance, or merge authority.

If exact route resolution or the same-turn polling return path cannot pass this
canary, T102 must not use the success terminal.

## Required Repository Changes

Implementation must at minimum:

1. update `docs/collaboration_workflow.md` with the authoritative direct
   notification, route-generation, polling, and authority rules;
2. update `docs/implementer_coordination.md` so Maintainer enters the protocol
   only after reading/verifying Implementer work and classifying a
   Planner-owned action;
3. add a concise `AGENTS.md` reminder;
4. keep one detailed normative protocol source rather than duplicating the full
   mechanics across documents;
5. include copyable templates for route assertion/advertisement, durable review
   request, direct notification, durable Planner response correlation, and
   Maintainer response ACK;
6. document manual fallback and the explicit non-persistent-resume limitation.

A small helper/test module is optional if useful for canonical assertion
serialization/hash validation or comment parsing. Do not build a new task
registry, message broker, authentication service, or workflow engine.

## Verification

Required verification includes:

- repository task/document guards pass;
- all changed documentation links resolve;
- one-task-one-PR authority remains unchanged;
- STSRL Implementer cannot bypass Main Maintainer by default;
- direct notification is explicitly non-authoritative;
- Planner route resolution requires role-aware exact assertion/hash matching;
- missing, multiple, unreadable, or stale route cases fail closed;
- cached thread ids are invalidated on generation change;
- request retry reuses one durable notification id;
- stale exact-head requests do not authorize review of a newer head;
- Planner response must be durable on the PR before Maintainer resumes;
- processed-response ACK prevents obvious replay on later recovery;
- active-turn polling can resume without user relay in the Phase-B canary;
- no claim of restart-safe automatic Maintainer recovery is made;
- manual user relay remains supported;
- the required duplicate-delivery and stale-generation canary cases pass.

If Python helper code is added:

```bash
pytest <focused tests>
python -m compileall -q src tests
ruff check <changed Python files>
ruff format --check <changed Python files>
```

Also report the ordinary supported repository documentation/test-suite outcome
used for final acceptance.

## Terminal Classification

Success terminal:

`AGENT_PLANNER_REVIEW_ROUTING_ESTABLISHED`

Use only if:

- Phase-A capability findings remain accurately represented;
- one current Planner route generation can be resolved uniquely through the
  demonstrated Codex list/read tools;
- exact-thread direct send/wakeup passes the Phase-B live canary;
- durable-first notification and exact-head verification are implemented;
- Planner decisions remain PR-authoritative;
- active-turn Maintainer sleep/poll observes the durable decision and resumes
  without user relay in the canary;
- duplicate notification delivery is idempotent;
- route supersession invalidates cached old routes;
- existing collaboration authority and final exact-head dual acceptance remain
  intact;
- required documentation/tests/canary evidence pass.

This terminal means:

> routine Planner-actionable reviews can be routed automatically to a uniquely
> resolved current Planner conversation within the exposed Codex candidate
> surface, and the same active Maintainer turn can resume from the durable PR
> response without user relay.

It does **not** mean:

- global/exhaustive discovery of every ChatGPT conversation;
- cryptographic Planner identity;
- automatic detection of an unannounced Planner replacement;
- restart-safe recovery after the Maintainer turn terminates;
- exactly-once transport delivery;
- Planner -> Maintainer direct push.

If the live canary cannot satisfy the success conditions, use `INCOMPLETE` and
report the exact missing transport capability rather than weakening the claim.

## Out Of Scope

Do not perform or authorize in T102:

- simulator/native/Search/model changes;
- scientific experiments;
- ChatGPT/Codex product API changes;
- credential/token publication;
- a custom authentication system;
- a persistent message broker;
- a new task/lifecycle database;
- fuzzy "most likely Planner" routing;
- silent use of superseded Planner generations;
- weakening exact-head dual final acceptance;
- claiming persistent Maintainer recovery that has not been demonstrated.

## Execution Freedom And Material Changes

Maintainer/Implementer may choose ordinary documentation layout, helper/module
names, parser implementation, and polling cadence within the bounded guidance.

Planner amendment and renewed exact-spec approval are required for any change
that would:

- remove role-aware exact route matching;
- allow fuzzy/recency-only Planner selection;
- allow STSRL Implementer to bypass Maintainer by default;
- make direct chat notification authoritative;
- remove durable PR request/response anchoring;
- remove exact-head checks;
- remove route-generation invalidation;
- claim restart-safe automatic resume without new demonstrated evidence;
- alter one-task-one-PR or dual-final-acceptance semantics.

## Acceptance And Authorization Boundary

Phase A is complete.

This Phase-B contract is now the candidate implementation specification.
Publication of this amendment does not itself authorize implementation.

Before implementation, Maintainer must independently review this exact Phase-B
head and post:

```text
SPEC APPROVED

task: T102
approved_spec_commit: <exact full Phase-B SHA>
implementation_authorized: true
```

Implementation then proceeds on the same PR.

Final landing requires:

- successful Phase-B non-authoritative live canary;
- Maintainer final implementation/operational acceptance;
- Planner final governance/architecture acceptance;

all on the same exact final PR head.
