# T102 Amendment: Per-Generation Planner Route Binding

Artifact Eligibility Required: false

This is a same-ID normative amendment to
`T102-agent-planner-notification-protocol.md`.

It supersedes only the parts of **Resolving The Current Planner** and **Cached
route** that can be read as requiring a complete conversation-universe scan
before every direct delivery.

All other T102 Phase-B semantics remain unchanged.

## Problem

The primary Phase-B text requires Main Maintainer, before every direct Planner
delivery, to enumerate the exposed conversation universe and inspect candidates
with `read_thread` to prove one exact assistant-authored route assertion.

That exhaustive discovery is justified when establishing a new route generation
because the demonstrated Codex surface has no global message-search primitive.
It is not justified as the normal cost of every later message within an
unchanged generation.

T102 therefore separates:

1. **route discovery/binding**, performed once when a route generation has no
   valid binding; and
2. **bound-route validation**, performed before ordinary later sends.

## Durable Route Binding

After exhaustive discovery finds exactly one valid route assertion for an
active generation, Main Maintainer posts one transient PR coordination comment:

```text
PLANNER_ROUTE_BINDING
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx or native work item>
pull_request: <number>
route_generation: <generation>
route_token: <token>
assertion_sha256: <sha256>
thread_id: <exact non-secret Codex/ChatGPT thread identifier>
status: BOUND
```

The binding is routing metadata only. It is not Planner identity, approval,
authority, lifecycle state, or a credential.

The thread identifier is treated as non-secret routing metadata. Do not persist
host credentials, tokens, cookies, or other authentication material.

At most one unsuperseded `BOUND` record may exist for one active route
generation. Ambiguous/multiple bindings fail closed.

## Route Discovery / Binding

A complete exposed-candidate scan is required only when:

- the current active route generation has no valid `BOUND` record;
- the active advertisement supersedes the bound generation/token/hash;
- the bound thread cannot be read;
- the bound thread no longer contains the exact assistant-authored current
  assertion;
- binding metadata is corrupt/ambiguous; or
- another protocol check gives concrete reason that the bound route is stale.

In that case Maintainer performs the primary contract's exhaustive discovery:

1. enumerate the candidate universe exposed by the demonstrated Codex tools;
2. use metadata only to prioritize reads, not as final routing authority;
3. inspect candidates with `read_thread`;
4. require exactly one role-aware canonical assertion/hash match;
5. fail closed on zero/multiple matches or an unreadable candidate needed to
   establish uniqueness;
6. post the `PLANNER_ROUTE_BINDING` only after uniqueness is established.

Because no global message-search primitive was demonstrated, this one-time
binding operation is inherently O(number of exposed candidate conversations).
That cost is accepted only at generation binding/recovery, not per message.

## Bound-Route Validation Before Ordinary Send

When the current active route generation has one valid `BOUND` record,
Maintainer must **not** rescan every visible conversation merely to send another
message.

Before each ordinary send it instead:

1. re-reads the task PR and latest active `PLANNER_ROUTE_ADVERTISEMENT`;
2. verifies the binding's repository/task/PR/generation/token/assertion hash
   exactly match that advertisement;
3. `read_thread`s only the bound `thread_id`;
4. verifies the exact current canonical assertion still occurs in an
   `agentMessage` of that thread;
5. sends only to that exact bound thread.

If those checks pass, the binding remains usable.

This optimization does not claim detection of hidden/unlisted duplicate
branches that the Phase-A tools cannot expose, nor detection of a silent Planner
replacement. Those non-claims remain unchanged.

## Planner Replacement

A deliberate Planner replacement still requires a new superseding route
generation.

As soon as Maintainer observes a new active generation/token/assertion hash:

- any old `PLANNER_ROUTE_BINDING` is invalid;
- the old cached thread must not be used;
- the new generation performs discovery/binding once;
- subsequent sends use bound-route validation.

A silent replacement without a superseding generation remains outside T102's
automatic guarantees.

## Retry And Same-Generation Requests

Transport retry of the same notification and later distinct Planner-actionable
requests within the same route generation reuse the valid binding.

Neither case triggers a full conversation scan unless bound-route validation
fails.

## Verification

Implementation/live canary must prove:

1. a fresh generation with no binding performs one exhaustive visible-candidate
   discovery and creates exactly one `PLANNER_ROUTE_BINDING`;
2. a second send in the same generation re-reads PR state and only the bound
   thread, without enumerating/reading the whole candidate universe;
3. generation supersession invalidates the old binding and forces one new
   discovery/binding;
4. corrupt/missing/multiple binding records fail closed;
5. a bound thread that loses/mismatches the assertion forces re-discovery;
6. no binding field is treated as Planner approval or merge authority.

Before final landing this amendment must either be folded into the primary T102
protocol document or be linked from the archive's T102 same-ID amendment lookup.
