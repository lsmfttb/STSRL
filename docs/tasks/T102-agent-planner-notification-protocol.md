# T102: Planner Review Routing and Maintainer Polling Protocol

Artifact Eligibility Required: false

## Objective

Establish a capability-grounded protocol for routine Main Maintainer -> Planner
review requests that:

1. routes the request to exactly one currently advertised Planner conversation
   using the Codex inter-thread capabilities proven in T102 Phase A;
2. anchors every request and authoritative decision in the task PR;
3. keeps direct chat traffic compact and non-authoritative;
4. lets Main Maintainer remain in the same active turn and detect the durable
   Planner decision through bounded PR polling without requiring user relay;
5. fails closed when route resolution, exact-head identity, or response
   correlation is ambiguous.

T102 does **not** claim restart-safe automatic recovery after the Maintainer turn
has terminated. Phase A proved only active-turn sleep/poll continuation.

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

Phase A demonstrated:

- `mcp__codex_app__list_threads({limit: 50})`;
- `mcp__codex_app__list_archived_threads(...)`;
- `mcp__codex_app__read_thread({threadId, ...})`;
- `mcp__codex_app__send_message_to_thread({threadId, prompt, ...})`;
- role visibility through `userMessage` / `agentMessage`;
- exact-thread send to one idle ChatGPT conversation and visible wake/response;
- `clock.sleep({duration_ms})` continuation in the same active Maintainer turn;
- PR state/comment reads after wake.

Phase A did **not** establish:

- global/exhaustive conversation search;
- authoritative Planner identity or branch lineage;
- automatic detection of a silent Planner replacement;
- Planner -> Maintainer direct push;
- restart-safe automatic Maintainer recovery after turn termination.

These limitations remain part of the Phase-B claim boundary.

## Authority Boundary

Routing, notification, polling, route assertions, advertisements, probes, and
ACKs are coordination only. None may by itself:

- approve a task specification;
- authorize implementation or scientific execution;
- create Maintainer final acceptance;
- create Planner final acceptance;
- authorize a merge;
- change task meaning;
- create a second lifecycle registry.

Authoritative task meaning remains in the task contract. Authoritative workflow
decisions remain durable exact-head PR records.

## Planner Route Generation

For every automated review channel, the active Planner emits this canonical
assistant-authored block in the Planner conversation:

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

The Planner also posts one durable PR comment:

```text
PLANNER_ROUTE_ADVERTISEMENT
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx or native work item>
pull_request: <number>
route_generation: <same generation>
route_token: <same token>
assertion_sha256: <sha256>
status: ACTIVE
supersedes: <prior advertisement comment id or none>
```

### Canonical assertion byte serialization

`assertion_sha256` is computed over exactly these bytes:

1. the assertion has exactly eight logical lines in the field order shown above;
2. each field line is ASCII key text, one colon, one space, then its UTF-8 value;
3. no leading or trailing whitespace is allowed on any line;
4. lines are joined with LF byte `0x0A`; CRLF is not canonical;
5. the serialized block ends with exactly one final LF byte;
6. there is no UTF-8 BOM;
7. Markdown fences, indentation outside the block, surrounding blank lines, and
   explanatory prose are excluded;
8. SHA-256 is computed over those UTF-8 bytes and rendered as 64 lowercase hex
   characters.

A parser must reconstruct exactly this serialization before hash comparison.
Different line endings, field order, missing final LF, extra whitespace, or BOM
must fail hash validation.

The route token is routing metadata, not a credential.

## Resolving The Current Planner

Before every direct Planner delivery, Main Maintainer must:

1. re-read the task PR;
2. resolve the latest unique unsuperseded `ACTIVE`
   `PLANNER_ROUTE_ADVERTISEMENT`;
3. enumerate the candidate universe exposed by the current Codex tools:
   - pinned/recent records through `list_threads` at the maximum supported
     limit;
   - every archived ChatGPT/Codex page reachable through
     `list_archived_threads` until each cursor is exhausted;
4. use list metadata only to prioritize reads, never as routing authority;
5. inspect candidates with `read_thread`;
6. count a match only when the exact canonical `PLANNER_ROUTE_ASSERTION`
   occurs in an `agentMessage`;
7. canonicalize it using the frozen byte rules and require SHA-256 equality;
8. require exactly one successfully inspected match;
9. send only to that exact returned conversation/thread id.

Fail closed if:

- there are zero or multiple exact assistant-authored matches;
- the PR advertisement is missing or ambiguous;
- any assertion field/hash differs;
- a plausible candidate necessary to establish uniqueness cannot be read;
- the PR/head no longer matches the durable request;
- the requested workflow action is already stale, closed, or merged.

Do not select by title, recency, summary, or "most likely Planner".

### Cached route

A resolved thread id may be cached only for the current route generation.
Before every send, Maintainer re-reads the PR advertisement. Any generation,
token, or supersession change invalidates the cache. Even without a generation
change, `read_thread` must reconfirm the current assertion before send.

## Planner Replacement / Handoff

T102 does not claim detection of a silent Planner replacement.

A deliberate replacement is made observable only when the replacement Planner:

1. reads the latest route generation;
2. increments the generation and creates a fresh token;
3. emits the new canonical assertion in the replacement conversation;
4. posts a new PR advertisement with `supersedes` naming the prior advertisement.

Maintainer re-reads PR state before every delivery, discards the cached old
thread on generation change, and resolves the new route.

Without a superseding generation, automatic replacement detection is unproven;
manual/user recovery is required.

## Durable Review Request

For STSRL the role route remains:

```text
Task Implementer -> Main Maintainer -> Planner
```

Task Implementer does not bypass Main Maintainer by default.

Before direct delivery, Maintainer first posts:

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

The request comment id is the durable notification id:

```text
notification_id = github-pr-comment:<request-comment-id>
```

Transport retries reuse that same durable request and notification id. A
materially changed head/request/evidence boundary requires Maintainer re-review
and a new durable request.

## Compact Direct Delivery

After route resolution, Maintainer sends only:

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

Do not copy full diffs, logs, task history, or long analysis into Planner
context. Planner retrieves durable evidence independently.

The send result is not authority or a delivery receipt. `read_thread` may be
used afterward to confirm that the notification appeared or was answered.

## Planner Handling And Deduplication

On receipt, Planner must:

1. re-read the PR and current route advertisement;
2. verify this Planner conversation still contains the current assertion;
3. fetch the durable request by notification id;
4. verify task/PR/phase/exact-head identity;
5. independently inspect required contract/diff/evidence;
6. check whether this durable request already has a valid Planner decision;
7. suppress duplicate review/merge action when already resolved.

Direct notification authorizes Planner to look, not to accept.

If the PR head advanced materially, Planner records a stale-request finding;
Maintainer must re-review and issue a new request for the new head.

## Durable Planner Decision

Planner records its authoritative response on the PR using the existing
workflow-specific format and includes:

```text
in_response_to_notification_id: github-pr-comment:<request-comment-id>
exact_head: <sha>
```

The PR decision is authoritative. No direct Planner -> Maintainer push is
required.

## Maintainer WAITING_FOR_PLANNER Polling

After direct delivery, Main Maintainer stays in the same active turn and enters
`WAITING_FOR_PLANNER`.

The Phase-A-proven return loop is:

```text
send notification
repeat while task-specific wait budget remains:
    clock.sleep(task_specific_bounded_interval)
    re-read PR state/head/current route/comments
    if matching durable Planner decision exists:
        validate it
        enter resume protocol
        stop polling
    if exact head changed materially:
        stop; request is stale
    if route generation changed and no decision exists:
        discard cached thread
        re-resolve current route
        resend the SAME notification_id
```

Polling cadence and total wait budget are task-specific operational choices.
They must be bounded and must avoid a tight loop. T102 defines **no default
seconds/minutes cadence** because Phase A established no latency requirement or
normal polling interval.

A response matches only when:

- it explicitly references the notification id;
- task/PR match;
- exact head matches for exact-head decisions;
- the decision format is valid under the existing workflow.

Direct chat text alone is never sufficient.

## Recoverable Resume Protocol

T102 does not use a `RESUMED` ACK as a promise that some later non-idempotent
action occurred.

After consuming a durable Planner decision, Maintainer derives a stable resume
operation id:

```text
resume_operation_id = sha256(
  "agent-planner-review-v1" || "\n" ||
  notification_id || "\n" ||
  planner_decision_comment_id || "\n" ||
  exact_head || "\n" ||
  resume_action_kind || "\n"
)
```

Automatic resume under T102 is permitted only for a follow-up whose completion
is **idempotent or durably observable before retry**.

Before attempting the follow-up, Maintainer must determine a completion
predicate. Examples:

- a specific PR comment with this `resume_operation_id` already exists;
- a specific exact-head workflow state already exists;
- a repository change with a stable identity already exists;
- the follow-up itself is read-only/idempotent.

If no reliable completion predicate exists for a non-idempotent follow-up,
T102 stops after observing the Planner decision and requires explicit/manual
recovery. It must not pretend exactly-once execution.

For an eligible automatic resume:

1. check the durable completion predicate;
2. if already complete, do not replay;
3. otherwise perform the idempotent/observable follow-up using the stable
   `resume_operation_id` where applicable;
4. re-check/observe completion;
5. only after completion is durably observable, post:

```text
MAINTAINER_PLANNER_RESPONSE_ACK
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<request-comment-id>
planner_decision_comment_id: <id>
exact_head: <sha>
resume_operation_id: <sha256>
resume_action_kind: <kind>
status: COMPLETED
completion_evidence: <durable predicate/evidence>
```

A later Maintainer session treats `COMPLETED` plus valid completion evidence as
proof not to replay. An ACK with missing/invalid completion evidence is not
sufficient.

### Interruption cases

The implementation/tests must cover both interruption windows:

- interruption **before** follow-up completion: no `COMPLETED` ACK exists, so a
  later session re-checks the completion predicate and may safely retry;
- interruption **after** follow-up completion but before ACK: a later session
  observes the durable completion predicate, does not replay the operation, and
  may then write the missing `COMPLETED` ACK.

This removes the ACK-before-action ambiguity identified in Maintainer review.

### Wait expiration / terminated turn

If the wait expires or the Maintainer turn terminates before response handling,
T102 does not claim automatic restart. A later user/manual-triggered Maintainer
session may recover from the durable request/decision/completion evidence.

## Direct-Delivery Trigger Policy

Use automated Planner notification only for genuine Planner-owned actions:

- material semantic/architecture decisions outside Maintainer execution
  freedom;
- final Planner review after Maintainer final acceptance;
- exceptional authority/landing ambiguity assigned to Planner;
- native-lane semantic/source review where the governing workflow assigns that
  review to Planner.

Do not notify Planner for every commit, routine test failures, ordinary
Implementer completion before Maintainer review, long-running progress, routine
canary/formal progress, or already-resolved requests.

## Manual User Requests

Manual user relay remains valid. If the user asks Planner to review the same
durable request, Planner uses the same notification-id/exact-head deduplication
rules.

## Duplicate / Branching Behavior

- A route generation must resolve to exactly one assistant-authored match.
- Duplicate Planner branches carrying the same current assertion cause route
  resolution to fail closed; no recency election is used.
- Request retry reuses one notification id.
- Existing durable Planner decision suppresses duplicate review.
- Planner handoff requires a new route generation.
- Hidden conversation branches outside the exposed enumeration surface are not
  claimed detectable.

## Phase-B Live Canary

Before final T102 acceptance, run one non-authoritative end-to-end canary:

1. Planner emits a fresh route assertion and matching advertisement;
2. Maintainer enumerates the real candidate set and resolves exactly one
   role-aware hash-valid match;
3. Maintainer sends a harmless exact-thread probe and Planner visibly answers;
4. Maintainer posts one durable canary review request and sends its compact
   notification;
5. Maintainer enters `WAITING_FOR_PLANNER` with a task-specific bounded poll
   interval and wait budget, with no user relay;
6. Planner posts one durable `T102_CANARY_DECISION` referencing notification id;
7. Maintainer observes the decision and performs only an idempotent/observable
   canary resume operation;
8. Maintainer posts `MAINTAINER_PLANNER_RESPONSE_ACK status: COMPLETED` only
   after durable completion is observable;
9. duplicate direct delivery produces no duplicate Planner decision;
10. a superseding route generation invalidates the cached old thread;
11. interruption is injected once before completion and once after completion
    but before ACK, and both recover without lost or duplicated follow-up.

The canary carries no specification approval, implementation authorization,
scientific result, final acceptance, or merge authority.

## Required Repository Changes

Implementation must at minimum:

1. update `docs/collaboration_workflow.md` with the authoritative route,
   notification, polling, resume, and authority rules;
2. update `docs/implementer_coordination.md` so Maintainer enters this protocol
   only after verifying Implementer work and classifying a Planner-owned action;
3. add a concise `AGENTS.md` reminder;
4. keep one detailed normative protocol source rather than duplicating full
   mechanics;
5. include copyable templates for route assertion/advertisement, durable review
   request, direct notification, Planner response correlation, and completed
   resume ACK;
6. document manual fallback and the non-restart-safe limitation.

A small helper/test module is optional for canonical assertion serialization,
hash validation, comment parsing, or resume-operation identity.

Do not build a new task registry, message broker, authentication service, or
workflow engine.

## Verification

Required verification:

- task/document guards pass;
- all changed documentation links resolve;
- one-task-one-PR authority remains unchanged;
- STSRL Implementer cannot bypass Main Maintainer by default;
- direct notification is explicitly non-authoritative;
- canonical assertion serialization is deterministic at the byte level;
- route resolution requires role-aware exact assertion/hash matching;
- missing/multiple/unreadable/stale route cases fail closed;
- cached thread ids are invalidated on generation change;
- request retry reuses one durable notification id;
- stale exact-head requests do not authorize newer-head review;
- Planner response is durable on PR before Maintainer resume;
- polling cadence is task-specific/bounded with no frozen short default;
- automatic resumed follow-up is limited to idempotent or durably observable
  operations;
- both interruption windows recover without lost/duplicated follow-up;
- active-turn polling resumes without user relay in the live canary;
- no claim of restart-safe automatic Maintainer recovery is made;
- manual user relay remains supported;
- duplicate-delivery and stale-generation canary cases pass.

If Python helper code is added:

```bash
pytest <focused tests>
python -m compileall -q src tests
ruff check <changed Python files>
ruff format --check <changed Python files>
```

Also report ordinary supported repository documentation/test-suite outcome.

## Terminal Classification

Success terminal:

`AGENT_PLANNER_REVIEW_ROUTING_ESTABLISHED`

Use only if:

- Phase-A capability findings remain accurately represented;
- one current Planner route generation resolves uniquely through the demonstrated
  Codex list/read tools;
- exact-thread direct send/wakeup passes the live canary;
- durable-first request and exact-head verification are implemented;
- Planner decisions remain PR-authoritative;
- active-turn Maintainer sleep/poll observes the durable decision without user
  relay;
- resume recovery passes both interruption cases without lost/duplicated
  eligible follow-up;
- duplicate notification delivery is idempotent;
- route supersession invalidates cached old routes;
- existing collaboration authority and dual exact-head final acceptance remain
  intact;
- required documentation/tests/canary evidence pass.

This terminal means routine Planner-actionable reviews can be routed
automatically to a uniquely resolved current Planner conversation within the
exposed Codex candidate surface, and the same active Maintainer turn can resume
from the durable PR response without user relay.

It does **not** mean:

- global/exhaustive conversation discovery;
- cryptographic Planner identity;
- automatic detection of silent Planner replacement;
- restart-safe recovery after Maintainer turn termination;
- exactly-once transport;
- Planner -> Maintainer direct push.

If the live canary cannot satisfy the success conditions, use `INCOMPLETE` and
report the exact missing transport capability.

## Out Of Scope

Do not perform or authorize in T102:

- simulator/native/Search/model changes;
- scientific experiments;
- ChatGPT/Codex product API changes;
- credential/token publication;
- custom authentication infrastructure;
- persistent message broker;
- new task/lifecycle database;
- fuzzy "most likely Planner" routing;
- silent use of superseded Planner generations;
- weakening exact-head dual final acceptance;
- claiming persistent Maintainer recovery not demonstrated in Phase A.

## Execution Freedom And Material Changes

Maintainer/Implementer may choose ordinary documentation layout, helper/module
names, parser implementation, and task-specific polling cadence.

Planner amendment and renewed exact-spec approval are required to:

- remove role-aware exact route matching;
- allow fuzzy/recency-only Planner selection;
- allow STSRL Implementer to bypass Maintainer by default;
- make direct chat notification authoritative;
- remove durable PR request/response anchoring;
- remove exact-head checks;
- remove route-generation invalidation;
- permit automatic non-idempotent resume without a durable completion predicate;
- claim restart-safe automatic resume without new demonstrated evidence;
- alter one-task-one-PR or dual-final-acceptance semantics.

## Acceptance And Authorization Boundary

Phase A is complete.

This Phase-B contract is the candidate implementation specification.
Publication of this amendment does not authorize implementation.

Before implementation, Maintainer must independently review the exact Phase-B
head and post:

```text
SPEC APPROVED

task: T102
approved_spec_commit: <exact full Phase-B SHA>
implementation_authorized: true
```

Implementation proceeds on the same PR only after that approval.

Final landing requires:

- successful non-authoritative Phase-B live canary;
- Maintainer final implementation/operational acceptance;
- Planner final governance/architecture acceptance;

all on the same exact final PR head.
