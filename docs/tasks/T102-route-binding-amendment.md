# T102 Amendment: Active-Set Planner Route Binding

Artifact Eligibility Required: false

This is a same-ID normative amendment to
`T102-agent-planner-notification-protocol.md`.

It supersedes the parts of **Resolving The Current Planner**, **Cached route**,
and the prior version of this amendment that require or permit widening route
discovery to the full visible/archived conversation history.

All other T102 Phase-B semantics remain unchanged.

## Core Rule

**Planner routing is resolved from the current active STS working set, never
from the user's accumulated conversation history.**

A current Planner is expected to be:

- an unarchived current ChatGPT conversation;
- in the STS project used by the live Planner workflow;
- freshly active for the newly published route generation; and
- explicitly claiming that exact generation through the canonical
  assistant-authored route assertion.

A conversation that does not satisfy those currentness conditions is not a
Planner candidate, even if old Planner/task text appears somewhere in its
history.

`list_archived_threads` MUST NOT be used for Planner routing or uniqueness
proof. Archived conversations are historical/inactive by definition for this
protocol. If the intended Planner has been archived, automatic routing fails
closed until an active Planner publishes a new generation.

T102 never falls back from current active candidates to archived or arbitrary
historical conversations.

## Route Generation Activation

A deliberate current Planner or replacement Planner activates a generation in
this order:

1. choose a fresh monotonically increasing `route_generation` and high-entropy
   `route_token`;
2. compute the canonical route assertion/hash under the primary T102 byte
   rules;
3. post one PR `PLANNER_ROUTE_ADVERTISEMENT` containing at least:

```text
PLANNER_ROUTE_ADVERTISEMENT
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
route_generation: <generation>
route_token: <token>
planner_project_id: <STS project id>
assertion_sha256: <sha256>
status: ACTIVE
supersedes: <prior advertisement id or none>
```

4. only **after GitHub has created that advertisement comment**, emit the exact
   canonical `PLANNER_ROUTE_ASSERTION` as an assistant-authored message in the
   intended current Planner conversation.

The GitHub advertisement comment's server `created_at` timestamp is the
`generation_activated_at` lower bound for candidate activity.

For the currently demonstrated STS Planner project, Phase A observed project id
`g-p-6a9985b51f44819186f65b74fe8af5da`. A later change of Planner project is a
routing-domain change and requires explicit Planner amendment/recovery; do not
silently search other projects.

The advertisement is transient routing metadata only. It is not Planner
approval, specification authority, or merge authority.

## Eligible Candidate Set

When a new active generation has no valid binding, Main Maintainer performs a
**bounded active-set discovery**, not a history scan.

It calls only the ordinary current-thread listing surface demonstrated in Phase
A (`list_threads` at its supported maximum). It MUST NOT call
`list_archived_threads` for route discovery.

Before any `read_thread`, discard every record that does not satisfy all of:

1. `kind == chatgpt`;
2. `projectId == planner_project_id` from the active advertisement;
3. the record is present in the ordinary unarchived `list_threads` result;
4. `updatedAt >= generation_activated_at`.

Title, preview, summary, generic words such as "Planner", and old task text are
not routing authority and MUST NOT widen the candidate set.

The temporal rule is intentional: because the protocol requires the route
assertion to be emitted only after the advertisement exists, a conversation
whose last activity predates generation activation cannot contain the current
generation assertion and cannot be the newly activated Planner.

A newly activated Planner should therefore appear near the recent end of the
current STS project working set even if the account contains years of unrelated
conversation history.

## Candidate Verification

Maintainer `read_thread`s only the eligible candidates above.

Reads must be bounded to recent turns sufficient to inspect post-activation
`agentMessage` content. Do not paginate into pre-activation/full conversation
history merely to search for routing text. If the exact current assertion is
not present in the bounded recent content, that candidate does not match.

A candidate matches only when:

- the exact canonical current-generation `PLANNER_ROUTE_ASSERTION` occurs in an
  `agentMessage`;
- repository/task/PR/generation/token/status fields match the PR advertisement;
- canonicalization reproduces `assertion_sha256`.

Exactly one eligible candidate must match.

- one match -> create the route binding;
- zero matches -> fail closed;
- more than one match -> fail closed as a duplicate/branched Planner ambiguity;
- a read failure that prevents deciding among otherwise eligible candidates ->
  fail closed.

**Fail closed means stop automatic routing and require explicit Planner/user
recovery or a fresh superseding generation. It does not mean search archived
threads, other projects, older conversations, or broader history.**

This protocol intentionally proves uniqueness only inside the semantically
eligible current working set exposed by the demonstrated tools. It does not
claim absence of hidden or historical copies of route text, because those are
not eligible current Planners.

## Phase-A Bootstrap For The Existing Planner

Phase A already live-proved the current Planner endpoint:

- thread id: `6aae4d69-bf5c-83e9-bc4f-492ea1086dcb`;
- kind: `chatgpt`;
- project id: `g-p-6a9985b51f44819186f65b74fe8af5da`;
- exact-thread send woke the idle conversation and produced the durable ACK in
  PR comment `5842971509`.

For the existing Planner generation, Maintainer may validate this exact
Phase-A-proven endpoint directly against the latest active advertisement and
current canonical assertion instead of rediscovering it.

If the proven endpoint no longer validates, do not scan historical/archived
threads. Publish/recover a fresh generation under the active-set procedure.

## Durable Route Binding

After exactly one eligible candidate is verified, Main Maintainer posts:

```text
PLANNER_ROUTE_BINDING
protocol_version: agent-planner-review-v1
repository: <owner/repo>
task: <Txxx>
pull_request: <number>
route_generation: <generation>
route_token: <token>
planner_project_id: <project id>
assertion_sha256: <sha256>
thread_id: <exact non-secret ChatGPT thread id>
status: BOUND
```

The binding is routing metadata only. It is not Planner identity in a
cryptographic sense, approval, lifecycle authority, or a credential.

At most one unsuperseded `BOUND` record may exist for one active generation.
Multiple/conflicting bindings fail closed.

## Bound-Route Validation Before Ordinary Send

Once a generation is bound, normal sends do not rediscover candidates.

Before every direct send Maintainer:

1. re-reads the PR and latest active `PLANNER_ROUTE_ADVERTISEMENT`;
2. invalidates the binding on any generation/token/project/hash/supersession
   change;
3. checks the bound thread still appears in the ordinary unarchived
   `list_threads` current surface with the expected `kind` and `projectId`;
4. `read_thread`s only the bound thread using a bounded recent-turn read;
5. verifies the exact current canonical assertion remains in an `agentMessage`;
6. sends only to that exact bound `thread_id`.

No other conversation content is read on the normal path.

If bound validation fails, automatic delivery fails closed and requires an
explicit fresh generation/recovery. It MUST NOT trigger a full-account or
archived-history scan.

## Planner Replacement / Handoff

A deliberate Planner replacement is cheap and explicit; it does not search for
"the new Planner" across history.

The replacement Planner:

1. posts a superseding advertisement with a fresh generation/token and the same
   STS `planner_project_id`;
2. after the advertisement exists, emits the corresponding canonical assertion
   in its own conversation.

Maintainer then:

1. sees the generation change on the PR and discards the old binding;
2. calls `list_threads` once;
3. filters to unarchived ChatGPT conversations in the STS project whose
   `updatedAt` is at/after generation activation;
4. reads only those eligible recent candidates;
5. requires exactly one canonical assertion match and binds it.

Thus replacement cost depends on the tiny set of **currently active STS project
conversations since the handoff**, not on total account history and not on the
number of old Planners.

A silent replacement with no superseding advertisement/assertion remains
outside T102's automatic guarantees.

## Why Archived Threads Are Excluded

Archiving is an explicit lifecycle signal that a conversation is no longer in
the ordinary current working set. An archived former Planner can contain exact
old task text, old assertions, and long histories, but none of that makes it the
current Planner.

Reading archived conversations for routing would:

- make cost grow monotonically with project age;
- increase false/duplicate matches from obsolete Planner generations;
- consume large irrelevant histories;
- weaken the semantic distinction between current work and retained history.

Accordingly, archived conversations are retained evidence/history only and are
never routing candidates under T102.

## Verification

Implementation/live canary must prove:

1. route discovery never calls `list_archived_threads`;
2. irrelevant current threads from other projects and non-ChatGPT kinds are
   filtered before any `read_thread`;
3. current STS threads whose `updatedAt` predates generation activation are
   filtered before any `read_thread`;
4. a fresh handoff generation reads only the remaining eligible current
   candidates and binds exactly one canonical assertion match;
5. zero/multiple eligible matches fail closed without widening search scope;
6. Phase-A-proven bootstrap can bind the existing Planner by validating only
   its exact known thread;
7. a second send in one generation reads only PR/current-list metadata and the
   bound thread, not unrelated conversations;
8. generation supersession invalidates the old binding and discovers the new
   Planner from the fresh active-set window only;
9. a bound thread becoming unavailable/archived/mismatched fails closed rather
   than triggering historical discovery;
10. no route advertisement/binding field is treated as Planner approval or
    merge authority.

Before final landing this amendment must either be folded into the primary T102
protocol document or be durably linked from the archive's T102 same-ID amendment
lookup.
