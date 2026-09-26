# T102: Planner Rendezvous, Review Notification, and Maintainer Resume Protocol

Artifact Eligibility Required: false

## Objective

Establish a repository-wide review-notification protocol that removes routine
manual user relay while using only capabilities that can be demonstrated in the
actual Planner/Maintainer environments.

The protocol must solve two separate problems:

1. **request routing:** a Maintainer or accepted native-lane sender must be able
   to identify the correct current Planner conversation and deliver one compact
   review request without guessing among unrelated or superseded conversations;
2. **requester continuation:** after Planner records the durable decision, the
   requesting Maintainer must resume automatically without requiring Planner to
   push a message into a Maintainer thread that Planner cannot address.

T102 therefore uses:

- **direct Agent -> Planner notification** only after an exact task-scoped
  Planner rendezvous has been resolved and live-proven;
- **durable PR decision + Maintainer coordination heartbeat/polling** for the
  Planner -> Maintainer return path.

T102 is governance/tooling work only. It does not change simulator, native,
Search, model, scientific-result, artifact-eligibility, or task-terminal
semantics.

## Publication Baseline

Publication base:

`main @ 1b9fd53b8708c0c328a795ca7ad87d4fe4648b99`

Task PR:

`#118`

Accepted predecessors:

- T100: `REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`.

T101 PR #117 is only an attribution/duplicate-delivery ambiguity example. It is
not classified as confirmed Agent impersonation or an unauthorized merge.

## Capability Findings That Constrain The Design

T102 must not assume capabilities that were not demonstrated.

At the Planner side used to publish this contract:

- GitHub PR read/write/review/merge tools are available;
- no effectful cross-thread `send_message`, `resume_thread`, or equivalent
  tool is exposed to Planner;
- Planner therefore cannot currently guarantee a direct push/wakeup into an
  arbitrary Maintainer session.

Consequently:

- a Planner -> Maintainer direct return route is **not** a T102 requirement;
- T102 must use a requester-owned waiting/polling mechanism for the return path;
- future availability of a Planner-side direct-send tool may optimize the
  protocol later, but T102 cannot depend on it.

The existing sts_lightspeed workflow provides evidence that some Codex-side
agents can discover/read other relevant threads and send direct review
requests. T102 does not treat that as established for STSRL merely by
assumption. The exact rendezvous discovery path must pass the live canary below
before the success terminal can be claimed.

## Core Authority Principle

**Transport is not authority.**

A direct notification, heartbeat wakeup, thread discovery result, rendezvous
record, or Planner receipt never by itself:

- approves a task specification;
- authorizes implementation;
- authorizes canary/formal scientific execution;
- records Maintainer final acceptance;
- records Planner final acceptance;
- changes task meaning;
- authorizes merge.

Existing durable exact-head workflow rules remain authoritative.

## STSRL Role Routing

Default route:

```text
Task Implementer -> Main Maintainer -> Planner
```

The STSRL Implementer does not bypass the Main Maintainer merely because
cross-thread communication exists.

The Main Maintainer may notify Planner only when Planner action is required,
including:

- exact-spec review;
- a real semantic/architecture decision outside Maintainer freedom;
- final governance/scientific/architecture review;
- a genuine exceptional authority/landing question.

Routine implementation progress, test output, job progress, and
Maintainer-owned diagnostics are not Planner notifications.

An accepted external native workflow may keep its existing direct native
Implementer/reviewer -> Planner semantic-review route where that workflow
already assigns Planner the review.

Manual user relay always remains a valid fallback.

## Planner Rendezvous: Concrete Meaning

A rendezvous is **not** a thread ID supplied by Planner.

Planner cannot currently read or publish its own thread/session identifier from
the available tool surface.

Instead, a rendezvous consists of:

1. one high-entropy random `rendezvous_nonce`;
2. one machine-searchable **assistant-authored endpoint assertion** containing
   that nonce in the active Planner conversation;
3. one durable PR comment that names the same nonce, route generation, and
   SHA-256 of the canonical assertion text.

Canonical active-conversation assertion:

```text
PLANNER_ENDPOINT_ASSERTION
protocol_version: agent-planner-notification-v1
repository: <owner/repo>
task: <task>
pull_request: <pr>
route_generation: <positive integer>
rendezvous_nonce: <random UUID/nonce>
status: ACTIVE
```

Durable PR record:

```text
PLANNER_RENDEZVOUS
protocol_version: agent-planner-notification-v1
repository: <owner/repo>
task: <task>
pull_request: <pr>
route_generation: <positive integer>
rendezvous_nonce: <same nonce>
assertion_sha256: <sha256 of canonical assertion text>
status: ACTIVE
supersedes: <prior rendezvous comment id or none>
```

The PR comment is transient task-transaction state, not a second durable task
registry.

The nonce is a routing discriminator, not a secret credential and not
cryptographic authentication.

## How A Sender Finds The Correct Planner

Before every direct Planner notification, the sender must:

1. re-read the task PR;
2. resolve the latest valid `PLANNER_RENDEZVOUS` generation;
3. discard any cached Planner thread if the generation/nonce changed;
4. use its available Codex inter-thread discovery/read tools to locate
   conversations containing the exact nonce;
5. require **exactly one** candidate conversation containing the exact canonical
   `PLANNER_ENDPOINT_ASSERTION` as an assistant-authored message;
6. canonicalize that assertion and require its SHA-256 to equal
   `assertion_sha256` from the PR;
7. only then use the discovered thread identifier/handle to send the compact
   review request.

If there are zero matches, multiple matches, no way to distinguish
assistant-authored content from copied/tool-output text, or the assertion hash
does not match, automated routing fails closed.

Do not:

- choose the most recent "Planner";
- search by conversation title only;
- choose the first thread that looks related;
- continue using an old cached Planner thread after rendezvous generation
  changes;
- probe arbitrary conversations until one responds.

The live canary must demonstrate the actual discovery tool sequence available
to the sender. If the current Codex environment cannot perform this exact
resolution, T102 must not claim that automated Planner discovery is solved.

## Planner Handoff / Replacement

Planner replacement is explicit.

A new Planner conversation must:

1. generate a new random nonce;
2. emit the new canonical `PLANNER_ENDPOINT_ASSERTION` in that new
   conversation;
3. post a new PR `PLANNER_RENDEZVOUS` with generation incremented by one and
   `supersedes` naming the prior rendezvous comment.

The old assertion remains historical evidence but is no longer routable.

Every sender re-reads the PR before every substantive delivery, so a generation
change invalidates its cached old Planner thread.

Immediately before recording an authoritative Planner decision, Planner must
also re-read the rendezvous and verify that its own assertion/generation is
still current. A decision posted after its Planner generation was superseded is
not a valid new Planner decision for that request and must be re-reviewed by
the current Planner.

A Planner decision recorded while its generation was current remains durable;
a later handoff does not retroactively invalidate it.

If rendezvous state is ambiguous, fall back to explicit user recovery rather
than guessing.

## Durable Review Request

Every automated request must first be anchored as a PR comment.

Required fields:

```text
PLANNER_REVIEW_REQUEST
protocol_version: agent-planner-notification-v1
sender_role: <Main Maintainer | accepted native sender>
repository: <owner/repo>
task: <task>
pull_request: <pr>
phase: <SPEC_REVIEW | MATERIAL_DECISION | FINAL_REVIEW | NATIVE_REVIEW | EXCEPTION>
exact_head: <40-char SHA>
rendezvous_generation: <generation>
rendezvous_nonce: <nonce>
requested_action: <one concise action>
material_delta: <short summary>
evidence_anchor: <durable PR evidence ids/paths>
authority: notification_only
```

The GitHub comment ID is the request identity:

```text
notification_id = github-pr-comment:<request-comment-id>
```

Transport retry must reuse this same notification ID. A timeout does not create
a new durable request.

If exact head, requested action, or material evidence boundary changes, create a
new durable request after the required review.

## Direct Agent -> Planner Envelope

After resolving the current rendezvous, the sender may send:

```text
PLANNER_NOTIFICATION
protocol_version: agent-planner-notification-v1
notification_id: github-pr-comment:<id>
repository: <owner/repo>
task: <task>
pull_request: <pr>
phase: <phase>
exact_head: <sha>
rendezvous_generation: <generation>
rendezvous_nonce: <nonce>
requested_action: <concise action>
evidence_anchor: <durable PR request comment>
authority: notification_only
```

The message is intentionally small. Do not copy full logs, full diffs, long
scientific arguments, or task history into the Planner thread.

The repository/PR remains the review context.

## Duplicate Direct Delivery

Direct request transport is at-least-once.

Before substantive review, Planner must:

1. fetch the durable request;
2. verify current PR/head/rendezvous;
3. check whether a Planner decision already exists for that request/head.

If unresolved, Planner may record:

```text
PLANNER_REVIEW_RECEIPT
notification_id: github-pr-comment:<id>
rendezvous_generation: <generation>
exact_head: <sha>
review_nonce: <opaque per-conversation nonce>
status: CLAIMED
```

If transport/network branching somehow delivers one request to more than one
Planner conversation sharing the same current rendezvous, the lowest GitHub
receipt-comment ID owns the review. Other branches stop before authoritative
decision or merge.

If endpoint discovery itself finds multiple exact assertion matches, do not use
receipt election as an excuse to guess. Fail closed and publish a fresh Planner
rendezvous for the intended branch.

## Planner Review And Durable Decision

Receiving a notification only authorizes Planner to inspect.

Planner independently verifies the required durable evidence, including as
appropriate:

- PR/base/head;
- task contract;
- Maintainer review record;
- changed files/diff;
- current `main`;
- scientific/provenance evidence.

Planner records the authoritative decision as the existing workflow requires.

A Planner decision comment responding to an automated request should include:

```text
notification_id: github-pr-comment:<request-comment-id>
rendezvous_generation: <current generation>
exact_head: <sha>
```

This lets the requester distinguish the intended durable response from unrelated
comments.

## Maintainer Resume: Polling, Not Planner Push

After sending the request, Main Maintainer must not terminate and require the
user to say "Planner replied" if its Codex environment supports recurring
coordination waits.

It enters:

`WAITING_FOR_PLANNER`

and uses a **coordination heartbeat / thread automation / bounded sleep-poll
loop** attached to its own Maintainer conversation.

Each wakeup polls the PR for:

- a Planner decision matching its `notification_id`, exact head, and current
  rendezvous generation;
- a Planner `CHANGES_REQUESTED`/material-decision response;
- PR head movement;
- rendezvous supersession;
- PR closure/merge or other transaction-ending state.

On a matching durable Planner decision, Maintainer resumes the same workflow,
re-fetches current PR/head, validates the decision, and continues.

This is distinct from an experiment heartbeat. T102 must update existing
coordination documentation so that "ordinary Planner waits" may use a
coordination heartbeat without being confused with long-running scientific-job
heartbeat semantics.

Polling cadence is an operational choice. It must be bounded and avoid
busy-waiting. Duplicate wakeups must be harmless.

If the Maintainer environment cannot schedule/resume the same thread or keep a
bounded wait loop alive, automated round-trip communication is not available in
that environment; fall back to manual user relay.

## Planner Replacement While Maintainer Waits

The Maintainer heartbeat always re-reads current rendezvous state.

If generation changes before a valid decision exists:

1. discard the cached old Planner thread;
2. resolve the new nonce/assertion;
3. re-send the **same durable request identity** to the new Planner only when
   request/head/material evidence are unchanged;
4. continue waiting.

Do not create a duplicate PR request solely because Planner changed.

If a valid durable Planner decision was recorded before supersession, consume
that decision and do not re-request it.

## Existing Decision Recovery

A surviving or newly discovered Planner should prefer durable decisions over
chat memory.

For the same request/head:

- existing valid Planner acceptance => do not repeat acceptance;
- existing changes-requested => wait for a new request/material head;
- already merged => at most bounded post-merge verification;
- unavailable historical chat attribution alone does not invalidate durable
  correct evidence.

## Required End-To-End Scenarios

### A. Normal round trip

Maintainer resolves current Planner nonce -> sends one durable/direct request ->
enters coordination heartbeat -> Planner reviews and posts durable decision ->
Maintainer heartbeat observes it and resumes without user relay.

### B. Request retry

Direct send result is uncertain -> same notification ID is resent to the same
current rendezvous -> Planner deduplicates.

### C. Wrong/irrelevant Planner conversation

Thread discovery returns a conversation with task-like text but no exact
assistant-authored assertion/hash -> reject it.

### D. Planner replacement

Generation 1 Planner is replaced -> generation 2 Planner emits a new nonce and
superseding PR rendezvous -> Maintainer re-reads PR, discards cached generation
1 thread, finds only generation 2, and routes there.

### E. Planner branch ambiguity

Discovery finds two exact assertion matches -> do not choose one by recency ->
explicitly establish a new rendezvous for the intended surviving Planner.

### F. Stale head

Request names H but PR is H2 -> Planner does not approve H2 from H's request ->
sender performs required review and creates a new request.

### G. Already resolved

A duplicate Planner delivery occurs after a valid durable decision -> recipient
observes the decision and performs no duplicate acceptance or merge.

### H. STSRL Implementer needs Planner input

Implementer reports to Maintainer -> Maintainer classifies -> only Maintainer
sends Planner request when truly Planner-owned.

## Live Capability Canary Required Before Success

T102 cannot succeed from prose alone.

Before final acceptance, perform a non-authoritative live canary using the
actual current environments.

Planner side:

1. current Planner emits a fresh endpoint assertion in its active conversation;
2. Planner posts the matching PR rendezvous comment.

Maintainer side:

3. Maintainer independently re-reads the PR;
4. using the actual Codex thread discovery/read tools available to it,
   Maintainer finds exactly one conversation matching the nonce and assistant
   assertion hash;
5. Maintainer sends a harmless canary notification to that discovered thread;
6. Maintainer enters its proposed coordination heartbeat/polling state.

Planner side:

7. the intended Planner conversation receives the canary without user relay;
8. Planner writes a harmless durable canary response comment on the PR.

Maintainer side:

9. heartbeat/polling wakes the original Maintainer conversation;
10. it finds the canary response and posts an ACK without user relay.

Also test:

- one duplicate request send;
- one unrelated/stale Planner thread that must not match;
- one superseding rendezvous generation, after which the old cached route is
  rejected.

The canary carries no spec approval, final acceptance, scientific authorization,
or merge authority.

If either exact Planner discovery or Maintainer heartbeat resume cannot be
demonstrated, leave T102 `INCOMPLETE` or amend the design. Do not claim success
from mocked/document-only tests.

## Required Repository Changes

Implementation must at minimum:

1. update `docs/collaboration_workflow.md` with the authoritative request,
   rendezvous, polling, and authority rules;
2. update `docs/implementer_coordination.md` to distinguish coordination
   heartbeat from experiment/job heartbeat and define WAITING_FOR_PLANNER;
3. add a concise summary to `AGENTS.md`;
4. add one detailed protocol document if useful, with the workflow remaining
   the authority index;
5. provide copyable templates for:
   - endpoint assertion;
   - PR rendezvous;
   - durable review request;
   - direct notification;
   - Planner receipt;
   - durable Planner decision binding;
   - Maintainer wait/poll/ACK;
6. document Planner handoff/supersession;
7. document manual user fallback.

Prefer one detailed normative source plus short references.

## Optional Lightweight Tooling

Small helpers/tests may support:

- canonical endpoint assertion serialization and SHA-256;
- rendezvous generation resolution;
- PR request/decision matching;
- duplicate notification detection;
- heartbeat polling state.

Do not build:

- a task database;
- a message broker;
- an authentication service;
- a large workflow engine;
- a second task state machine.

## Verification

Required focused verification:

- task/document guards pass;
- links resolve;
- one-task-one-PR authority remains unchanged;
- notifications/rendezvous never grant authority themselves;
- STSRL Implementer does not bypass Maintainer;
- Planner discovery requires exact current generation + nonce +
  assistant-authored assertion hash;
- ambiguous or missing rendezvous fails closed;
- old cached Planner thread is invalid after generation changes;
- Planner decision must bind request ID/head/current generation;
- Maintainer wait resumes from durable PR decision without user relay in the
  live canary;
- duplicate request send is idempotent;
- manual user relay remains valid;
- no unsupported Planner -> Maintainer direct-send capability is assumed.

If helper Python is added:

```bash
pytest <focused tests>
python -m compileall -q src tests
ruff check <changed Python files>
ruff format --check <changed Python files>
```

Report the supported repository doc/test suite result used for final acceptance.

## Terminal Classification

Success terminal:

`AGENT_PLANNER_REVIEW_RENDEZVOUS_ESTABLISHED`

Use only if:

- the current Planner can concretely publish a nonce/assertion rendezvous;
- the actual sender environment can resolve exactly that current Planner;
- Planner handoff/supersession changes future routing to the new Planner;
- request delivery is durable-first and idempotent;
- Maintainer can remain/re-enter WAITING_FOR_PLANNER and detect the durable
  Planner response without user relay;
- live canary demonstrates the complete round trip;
- notification versus authority remains explicit;
- existing exact-head acceptance/merge rules are unchanged.

If the current product/tool surfaces cannot satisfy the live canary, T102 is
`INCOMPLETE`; do not replace missing capability with a fictional route field.

## Explicit Non-Claims

T102 does not establish:

- cryptographic Planner identity;
- exactly-once message delivery;
- Planner-side arbitrary cross-thread send/resume capability;
- universal discovery when no valid rendezvous exists;
- recovery of lost chat history;
- proof of which historical branch authored an old comment;
- automatic scientific approval;
- automatic merge authority;
- a requirement to stop using manual user relay.

## Out Of Scope

Do not perform or authorize:

- simulator/native/Search/model work;
- scientific experiments;
- T101 reinterpretation;
- external authentication infrastructure;
- ChatGPT/Codex product API changes;
- guessing unrelated Planner conversations;
- weakening exact-head dual acceptance.

## Execution Freedom And Material Changes

Maintainer/Implementer may choose:

- exact documentation layout;
- concrete Codex discovery commands available in their environment;
- heartbeat cadence/backoff;
- helper/test structure.

Planner amendment and renewed exact-spec approval are required if implementation
would:

- replace nonce/assertion discovery with fuzzy Planner search;
- assume a Planner-side direct return-send capability not demonstrated here;
- remove live discovery/polling canary;
- allow STSRL Implementer to bypass Maintainer;
- grant notification/heartbeat authority;
- alter one-task-one-PR or exact-head acceptance semantics;
- add a new external service/credential.

## Acceptance And Authorization Boundary

Publishing/amending T102 does not authorize implementation.

Maintainer must independently review the exact contract head and record:

```text
SPEC APPROVED

task: T102
approved_spec_commit: <exact full SHA>
implementation_authorized: true
```

Final landing requires Maintainer final implementation/operational acceptance
and Planner final governance/architecture acceptance on the same exact final
head.

T102 itself continues to use the pre-T102/manual review path for authoritative
spec/final approval. Non-authoritative capability canary traffic is allowed
solely to prove the transport assumptions.
