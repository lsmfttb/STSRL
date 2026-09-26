# T102: Agent-Planner Transport Capability Discovery and Review Notification Protocol

Artifact Eligibility Required: false

## Objective

T102 must first discover the **actual** cross-conversation capabilities available
to the STSRL Main Maintainer / Codex environment before defining any automated
Maintainer -> Planner routing protocol.

The task exists to remove routine user relay only when the real tool surface can
support that safely.

T102 therefore has two phases:

1. **Phase A — capability discovery**
   - Maintainer reports exactly how its environment can enumerate, identify,
     read, address, and message Planner conversations, if at all;
   - Maintainer reports how it can wait for / poll a durable Planner response
     and resume work without user relay;
   - no discovery algorithm is assumed in advance.

2. **Phase B — protocol implementation**
   - Planner amends this same task contract using the demonstrated capabilities;
   - Maintainer then performs ordinary exact-spec review;
   - implementation proceeds only after the amended exact head receives
     `SPEC APPROVED`.

T102 must not invent a thread ID, route handle, nonce-search mechanism,
rendezvous registry, wakeup API, or Planner -> Maintainer push path that has not
been demonstrated in the actual environment.

## Publication Baseline

Publication base:

`main @ 1b9fd53b8708c0c328a795ca7ad87d4fe4648b99`

At publication there are no other open task PRs.

Accepted governance predecessors:

- T100: `REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`;
- T101: `SUPPORTED_COHORT_INSUFFICIENT`.

T102 is governance/tooling work only. It does not change simulator, native,
Search, training, scientific-result, artifact-eligibility, or scientific task
semantics.

## Motivation

The desired workflow is:

```text
Maintainer needs Planner action
    -> Maintainer reaches the correct current Planner automatically
    -> Planner reviews durable exact-head evidence
    -> Planner records durable decision on the PR
    -> Maintainer notices that durable decision and resumes automatically
```

The current project already knows that user relay can work. T102 asks whether
the same round trip can be made automatic with the tools that really exist.

Two questions must be answered before protocol design:

1. **How can Maintainer identify and message the correct current Planner?**
2. **After Planner records a response, how can Maintainer resume without the
   user manually saying "Planner replied"?**

The first question is not answered by writing "rendezvous" in a document. The
mechanism must be demonstrated.

## Known Capability Boundary At Publication

The current Planner tool surface has been inspected.

Planner can:

- read and write GitHub PR comments;
- independently inspect exact PR/head/repository evidence.

Planner currently cannot demonstrate an effectful tool that:

- sends a message into an arbitrary Maintainer conversation/thread;
- wakes/resumes a specific Maintainer session;
- returns this Planner conversation's own stable thread/session identifier for
  another Agent to address.

Therefore Phase A must **not** assume Planner -> Maintainer push.

The expected fallback, if Maintainer can message Planner but Planner cannot
message Maintainer, is:

```text
Maintainer -> Planner direct notification
Planner -> durable PR decision
Maintainer -> heartbeat / bounded polling of PR -> resume
```

But even this fallback is not frozen until Maintainer demonstrates its actual
discovery/send and polling capabilities.

## Authority Boundary

**Communication is not authority.**

A direct message, thread discovery result, polling wakeup, GitHub comment
notification, or future rendezvous mechanism must never by itself:

- approve a task specification;
- authorize implementation;
- authorize scientific execution;
- create Maintainer final acceptance;
- create Planner final acceptance;
- authorize a merge;
- change task meaning;
- create a second lifecycle registry.

Existing exact-head workflow authority remains unchanged.

## Phase A — Maintainer Capability Discovery

Phase A is part of Maintainer feasibility/spec review. It is **not**
implementation authorization.

Maintainer may inspect its real Codex/Agent tool surface and perform harmless
non-authoritative transport probes. It must not modify repository governance,
task semantics, or scientific code during Phase A.

### A1. Inter-conversation discovery inventory

Maintainer must report the exact available operations/tools for all applicable
capabilities:

- list/enumerate conversations, threads, sessions, agents, or turns;
- search/filter them;
- read conversation metadata;
- read message history or individual turns;
- distinguish assistant-authored messages from user/tool/copied text;
- obtain stable thread/session/host identifiers;
- send a message to a specific existing conversation/thread;
- determine whether sending wakes an idle/dormant conversation;
- observe send/delivery failure;
- inspect parent/child or project relationship metadata if available.

For every relevant operation report:

```text
tool_or_operation:
arguments_needed:
identifier_returned_or_consumed:
scope:
can_read_message_roles: true|false
can_target_exact_thread: true|false
can_wake_target: true|false|unknown
persistence_across_turns:
important_limitations:
```

Use exact tool/operation names from the real environment. Do not paraphrase a
capability that was not actually exposed.

### A2. "Find the Planner" feasibility report

Maintainer must answer, from observed capability rather than assumption:

- What candidate universe can it search?
- What stable identifier does a candidate Planner conversation expose?
- Can it distinguish the current STSRL Planner from:
  - an old/superseded STSRL Planner conversation;
  - a Planner for another repository/project;
  - an unrelated conversation containing copied task text;
  - another branch created by duplicate user/network delivery?
- Can it inspect message **roles**, or only text?
- Can it search exact assistant-authored markers without confusing tool output
  or quoted/copy-pasted text?
- Can it address the selected conversation directly once found?
- Can it prove a stale Planner route is stale?
- If the active Planner changes, what observable signal could make Maintainer
  stop using the old target?

Maintainer must recommend the simplest discovery strategy supported by the
actual tools.

Possible outcomes include, but are not limited to:

- direct exact thread/session ID supplied by the platform;
- project-scoped thread enumeration plus exact metadata filtering;
- a task/PR marker published in Planner conversation and resolved through
  role-aware thread search;
- no safe automated discovery mechanism.

T102 does **not** prefer one outcome in advance.

### A3. Harmless Planner discovery probe

If Maintainer believes it can identify the current Planner, it must perform one
non-authoritative live probe.

The probe payload must contain:

```text
T102_PLANNER_DISCOVERY_PROBE

task: T102
pr: 118
candidate_spec_head: <current exact head>
probe_id: <fresh random id>
authority: none
request: acknowledge this probe only; do not approve or merge anything
```

Maintainer must report:

- exact discovery operations used;
- number of candidate conversations inspected;
- number of matches;
- exact non-secret target identifier, if safe to record;
- why that target was considered the current Planner;
- whether the message send succeeded;
- whether the target was visibly awakened/responded;
- any ambiguity.

If the environment cannot safely identify exactly one target, do not guess and
do not send. Report `PLANNER_DISCOVERY_UNPROVEN`.

### A4. Maintainer waiting/resume capability

Maintainer must report the actual mechanism available to avoid user relay after
it sends a Planner request.

Investigate at least:

- whether the same Maintainer session can remain in a wait/sleep state;
- whether a scheduled/heartbeat/thread-automation wakeup exists;
- whether a bounded loop can poll PR comments/state;
- whether the session can resume execution after a poll observes a matching
  Planner decision;
- what happens if the Maintainer turn/session terminates;
- practical minimum/normal polling cadence;
- how duplicate polls/restarts would avoid duplicate follow-up actions.

A valid design may use polling. Planner -> Maintainer direct push is not
required.

If the actual environment cannot preserve or resume a Maintainer workflow
without user input, report `MAINTAINER_AUTO_RESUME_UNPROVEN`.

### A5. Phase-A durable report

Maintainer must post one PR comment:

```text
T102 CAPABILITY DISCOVERY REPORT

task: T102
reviewed_spec_head: <exact head>

planner_discovery:
  status: PROVEN | UNPROVEN | AMBIGUOUS
  exact_operations: ...
  candidate_scope: ...
  stable_target_identifier: ...
  role_awareness: ...
  send_capability: ...
  wake_behavior: ...
  stale_target_detection: ...
  replacement_strategy_possible: ...

maintainer_resume:
  status: PROVEN | UNPROVEN
  mechanism: ...
  polling_source: ...
  cadence_or_trigger: ...
  same_workflow_resumes: ...
  duplicate_suppression: ...

live_probe:
  attempted: true|false
  probe_id: ...
  target_identifier: ...
  outcome: ...

recommended_protocol:
  ...

blockers:
  ...
```

The report must distinguish observed facts from recommendations.

## Phase-A Decision Gate

After the capability report, **Planner decides the Phase-B architecture**.

Maintainer must not record `SPEC APPROVED` for protocol implementation before
Planner amends this task contract to a concrete mechanism based on the report.

Possible Planner decisions:

### Case 1 — discovery + send are proven; polling/resume is proven

Planner may freeze:

```text
Maintainer -> exact Planner direct message
Planner -> durable PR decision
Maintainer -> polling/heartbeat -> resume
```

No Planner -> Maintainer push is required.

### Case 2 — discovery/send are proven; automatic Maintainer resume is not

T102 cannot claim removal of user relay in both directions. Planner may either:

- amend the goal to one-way notification only; or
- leave T102 incomplete until a viable resume mechanism exists.

### Case 3 — safe Planner discovery is not proven

Do not implement a fuzzy "find Planner" heuristic.

Planner may choose a different architecture, for example:

- user-supplied explicit Planner handle when one exists;
- PR-only polling with no direct Planner wakeup;
- an external supported coordination mechanism;
- `INCOMPLETE` if no safe automation exists.

### Case 4 — exact platform route exists

If Maintainer discovers a real platform-issued exact Planner
thread/session/agent handle, prefer that over an invented marker/search
protocol, subject to replacement and stale-handle behavior being understood.

## Phase B — Protocol Requirements

These requirements are intentionally abstract until Phase A completes.

The amended Phase-B contract must define, using demonstrated capabilities:

1. how the requester identifies the current Planner;
2. how Planner replacement invalidates the old target;
3. how the request is anchored to durable PR evidence;
4. how duplicate/retried request delivery is deduplicated;
5. how Planner independently verifies exact head before authority;
6. how Planner records the durable response;
7. how Maintainer notices the response and resumes;
8. how stale-head, stale-Planner, duplicate-conversation, and restart cases fail
   closed;
9. how manual user relay remains a valid fallback;
10. how payload size is bounded so Planner context is not polluted.

Do not create a second task database or lifecycle registry.

## Role Routing

For STSRL, preserve:

```text
Task Implementer -> Main Maintainer -> Planner
```

Task Implementer does not bypass Main Maintainer merely because direct Planner
messaging may exist.

For an external native lane such as `sts_lightspeed`, direct notification by
the role already assigned to independent Planner/native review may remain
allowed if that repository's workflow permits it.

T102 does not change those authority assignments.

## T101 Attribution Example

T101 PR #117 remains only an example of ambiguous conversation attribution.

The project does not claim that a Maintainer or Agent impersonated Planner.
Duplicate user delivery / network-created Planner branches are a plausible
explanation.

T102 should solve future routing/retry ambiguity without rewriting T101
history.

## Required Repository Changes After Phase-A Amendment

Only after Planner freezes Phase B, implementation may update:

- `docs/collaboration_workflow.md`;
- `docs/implementer_coordination.md`;
- concise `AGENTS.md` reminders;
- one detailed notification/coordination document if useful;
- minimal helper/tests only if the demonstrated transport benefits from them.

Prefer one detailed normative source and references from other docs.

## Out Of Scope

Do not perform or authorize in T102:

- simulator/native/Search/model changes;
- scientific experiments;
- ChatGPT/Codex product API changes;
- invented cross-thread APIs;
- credential/token publication;
- a custom authentication service;
- a persistent message broker;
- a large workflow engine;
- fuzzy routing to "the most likely Planner";
- weakening exact-head dual final acceptance.

## Phase-A Verification

Before Planner freezes Phase B, require:

- exact current PR/head is recorded;
- exact real tool/operation names are reported;
- unsupported capabilities are explicitly marked unavailable/unknown;
- a harmless live discovery probe is attempted only if unique safe targeting is
  believed possible;
- no arbitrary Planner conversation is contacted after ambiguous discovery;
- Maintainer waiting/polling capability is tested or explicitly reported
  unavailable;
- no `SPEC APPROVED` is posted for implementation yet.

## Terminal Classification

T102 does not have a success terminal until Phase B is amended.

During Phase A, the task remains `READY` / in review.

After Planner receives the capability report, Planner must amend this section
with the concrete Phase-B success terminal and acceptance checks.

If no safe architecture can satisfy the desired automation, Planner may define
an `INCOMPLETE` terminal rather than pretending unsupported transport exists.

## Acceptance And Authorization Boundary

Current publication authorizes only:

- Maintainer independent review of this discovery contract;
- inspection of its real coordination tool surface;
- harmless non-authoritative Phase-A probes;
- the durable `T102 CAPABILITY DISCOVERY REPORT`.

It does **not** authorize repository implementation of the final protocol.

After Phase A:

1. Planner amends this task contract with the concrete Phase-B mechanism;
2. Maintainer independently reviews the new exact head;
3. only then may Maintainer record:

```text
SPEC APPROVED

task: T102
approved_spec_commit: <amended exact full SHA>
implementation_authorized: true
```

Final landing still requires Maintainer final implementation/operational
acceptance and Planner final governance/architecture acceptance on the same
exact final head.
