# T102 Amendment: Metadata-Current Planner Routing

Artifact Eligibility Required: false

This is a same-ID normative amendment to
`T102-agent-planner-notification-protocol.md`.

It supersedes all T102 routing requirements that depend on:

- `PLANNER_ROUTE_ASSERTION` content;
- assertion hashes or canonical assertion bytes;
- route generations or route tokens;
- `PLANNER_ROUTE_ADVERTISEMENT` for endpoint selection;
- `PLANNER_ROUTE_BINDING` as a persistent selected endpoint;
- `read_thread` for Planner discovery or route validation; or
- content/history search to decide which Planner conversation is current.

Those earlier mechanisms remain historical T102 design/canary evidence only.
They are not part of the current routing contract.

All non-routing T102 semantics remain unchanged, including durable PR request
identity, notification-not-authority, exact-head Planner verification, durable
Planner PR response, Maintainer polling/resume, and resume-operation
idempotency.

## Core Model

**The current Planner is a current STS ChatGPT work conversation, not a piece of
text hidden somewhere in conversation history.**

The demonstrated Codex thread-list metadata already exposes the information
needed for routing:

- exact thread id;
- `kind`;
- `projectId`;
- current/unarchived membership through the ordinary `list_threads` surface;
- `updatedAt`.

T102 therefore treats Planner routing as a metadata-currentness problem.
Conversation content is not needed to route a notification.

For the currently demonstrated STS Planner domain, the exact project id is:

`g-p-6a9985b51f44819186f65b74fe8af5da`

A future change of the STS Planner project id is a routing-domain change and
requires an explicit workflow/task amendment before automatic routing uses the
new project.

## STS Project Role Invariant

T102 relies on this project-level invariant:

> Ordinary unarchived `kind=chatgpt` conversations in the STS project are
> Planner-capable user-facing work conversations for this workflow.

Main Maintainer / Task Implementer execution conversations are not selected by
this rule because their thread kind/project surface is different from the STS
Planner ChatGPT surface demonstrated in Phase A.

If the STS project is later used to host ordinary unarchived ChatGPT
conversations that must **not** be Planner-capable, this invariant no longer
holds and T102 routing must be amended before relying on metadata-current
selection. Do not silently reintroduce title/content heuristics.

## Current Planner Selection

Immediately before **every** direct Planner notification, Main Maintainer:

1. calls the ordinary current `list_threads` surface demonstrated in Phase A;
2. does **not** call `list_archived_threads`;
3. filters records to all of:
   - `kind == chatgpt`;
   - `projectId == g-p-6a9985b51f44819186f65b74fe8af5da`;
   - present in the ordinary current/unarchived listing;
4. compares only thread-list metadata and finds the maximum `updatedAt` among
   the eligible records;
5. requires that the maximum identify exactly one thread;
6. sends the compact notification only to that exact thread id using the
   demonstrated exact-thread send operation.

No `read_thread` is required or permitted for route selection.

No title, preview, summary, task text, role word, assertion, nonce, hash, or old
message content participates in current-Planner selection.

### Fail-closed cases

Automatic routing stops and requires explicit user/Planner recovery when:

- there are zero eligible current STS ChatGPT threads;
- the maximum `updatedAt` cannot be resolved to exactly one eligible thread;
- required thread-list metadata is missing or malformed;
- the selected exact-thread send reports failure; or
- the STS project-id invariant is known to have changed.

Fail closed does **not** mean widening the search to:

- archived threads;
- another project;
- older conversation history;
- title/summary matching; or
- content/assertion search.

## Why Latest `updatedAt` Is The Handoff Signal

The user changes the operational Planner by interacting with a different STS
Planner conversation.

That interaction updates the new conversation's `updatedAt`. On the next
Planner-actionable notification, Maintainer re-lists current STS ChatGPT
threads and naturally selects the newly active conversation.

Therefore Planner replacement does not require a separate route-generation
protocol or a durable thread binding.

This also handles the common duplicate/network-branch case proportionally:
when more than one STS Planner branch exists, the branch the user continues to
use becomes the most recently updated current branch. If metadata cannot
produce a unique latest branch, the protocol fails closed rather than guessing.

Archiving provides an even stronger lifecycle signal: once a former Planner
conversation is archived, it is outside the ordinary current candidate surface
and can never be selected by T102 routing.

## No Durable Route Binding

T102 intentionally does not persist a normal-path Planner thread id in a
`PLANNER_ROUTE_BINDING` record.

The metadata lookup is cheap and re-running it before every direct delivery has
an important semantic benefit: endpoint replacement is detected through normal
currentness rather than through a stale cache plus invalidation machinery.

A caller may hold the selected thread id only for the duration of one concrete
send attempt.

Before a later distinct notification, it must re-run current Planner selection.

If a send fails and the sender chooses to retry, it may perform one fresh
metadata selection and resend the **same durable notification id**. Retry must
not create another PR review-request comment solely because the endpoint
changed.

## Relationship To Durable Review Requests

Endpoint selection answers only:

> Which current STS Planner conversation should be notified?

It does not answer:

> Has Planner approved anything?

Before direct delivery, Maintainer still posts the durable PR review-request
comment required by the primary T102 contract. Its GitHub comment id remains
the notification/idempotency identity.

The direct thread message remains a compact wakeup pointer to that durable PR
request. It grants no specification approval, implementation authorization,
final acceptance, scientific authority, or merge authority.

The receiving Planner independently fetches and verifies repository/PR/exact
head evidence before recording any authoritative decision.

## Planner Response And Maintainer Resume

This amendment does not add Planner -> Maintainer push.

Planner records its authoritative response durably on the PR.

The requesting Maintainer remains in the demonstrated same-active-turn bounded
wait/poll path and resumes only after observing and validating the matching
durable Planner response.

The resume-operation identity/idempotency amendment remains fully applicable.

T102 still does not claim restart-safe unattended recovery after a Maintainer
turn/session has terminated.

## Archived Conversations

`list_archived_threads` is forbidden for T102 Planner routing.

An archived conversation is retained history, not a current work endpoint.
Searching archived threads would both contradict that lifecycle signal and make
routing cost/error surface grow with project age.

The number or length of archived conversations must have zero effect on normal
T102 routing cost.

## Historical Assertion/Generation Records

Earlier T102 PR comments containing `PLANNER_RENDEZVOUS`,
`PLANNER_ROUTE_ADVERTISEMENT`, `PLANNER_ROUTE_ASSERTION`, route tokens,
assertion hashes, or bindings are retained only as historical design/canary
records.

They must not override the metadata-current selection rule in this amendment
and must not be consulted to choose the current Planner endpoint.

## Verification

Implementation and the live canary must prove at least:

1. Planner routing calls ordinary current `list_threads` but never
   `list_archived_threads`;
2. routing does not call `read_thread` for discovery/identity verification;
3. non-ChatGPT and other-project records are eliminated using metadata only;
4. among eligible current STS ChatGPT records, the unique maximum `updatedAt`
   thread is selected;
5. zero eligible records and non-unique/ambiguous maximum-currentness fail
   closed without content/history fallback;
6. direct delivery uses only the selected exact thread id and the durable PR
   notification id;
7. a later notification re-runs metadata selection rather than trusting a
   durable/cached Planner binding;
8. when another STS Planner conversation becomes more recently updated, the
   next selection chooses that conversation without scanning old content;
9. an archived former Planner is never considered;
10. duplicate transport delivery reuses the same durable notification id;
11. the direct notification remains non-authoritative and Planner authority is
    derived only from independently verified durable PR evidence;
12. Maintainer can remain in the approved bounded polling path, observe the
    matching durable Planner response, and resume without user relay.

The live canary does not need to manufacture a second Planner conversation if
that is operationally inconvenient. The implementation must at minimum test
the replacement selection rule with metadata fixtures, while the live canary
must prove metadata-only selection of the actual current Planner, exact-thread
wake delivery, durable PR response, and Maintainer poll/resume.

Before final landing this amendment must either be folded into the primary T102
protocol document or remain durably linked from the archive's T102 same-ID
amendment lookup.
