# T102 Resume-Operation Identity Amendment

This file is a normative same-ID amendment to
`T102-agent-planner-notification-protocol.md`.

It supersedes only the `resume_operation_id` derivation and the fields that bind
that identity in the `Recoverable Resume Protocol`. All other T102 Phase-B
semantics remain unchanged.

The amendment exists because the prior candidate head
`5a87699d298b16dff555bbab9c0416d69e3ad5b2` specified a conceptual SHA-256
concatenation but did not freeze the byte serialization or distinguish multiple
follow-up operations under one Planner decision.

## Canonical Resume Operation Identity

Every automatically resumable follow-up has two explicit action-identity
fields:

- `resume_action_kind`: an operation class matching exactly
  `[A-Z][A-Z0-9_]{0,63}`;
- `resume_action_key`: an operation-specific stable key matching exactly
  `[A-Za-z0-9._:/@#-]{1,160}`.

`resume_action_kind` is not free-form prose. Examples of valid kinds include
`POST_RESPONSE_ACK`, `POST_REVIEW_REQUEST`, `MERGE_PR`, and `READ_ONLY_VERIFY`.
These examples do not grant authority for those actions; existing workflow
rules still decide whether a follow-up is permitted.

`resume_action_key` must bind the specific intended follow-up, not merely its
class. It must be derived from stable durable target/parameter identity known
before the follow-up. For example, a PR-scoped operation may include repository,
PR number, exact head, or a stable logical marker name as applicable.

If one Planner decision can lead to more than one follow-up, every distinct
follow-up must use a distinct `(resume_action_kind, resume_action_key)` pair.
The same pair must not be reused for semantically different operations.

## Frozen Serialization

The canonical identity record is exactly these seven logical lines in this
field order:

```text
RESUME_OPERATION_IDENTITY
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<request-comment-id>
planner_decision_comment_id: <decimal-comment-id>
exact_head: <40-lowercase-hex-sha>
resume_action_kind: <validated-action-kind>
resume_action_key: <validated-action-key>
```

The byte serialization rules are:

1. the record contains exactly the seven logical lines above, in exactly that
   order;
2. literal field names and punctuation are ASCII exactly as shown;
3. every field line is `key`, one colon byte, one ASCII space byte, then the
   validated value;
4. `notification_id` is exactly `github-pr-comment:` followed by a base-10
   positive GitHub comment id with no leading plus sign or whitespace;
5. `planner_decision_comment_id` is base-10 positive digits only;
6. `exact_head` is exactly 40 lowercase hexadecimal ASCII characters;
7. `resume_action_kind` and `resume_action_key` must satisfy their grammars
   above before serialization;
8. there is no leading or trailing whitespace on any line and no blank line;
9. lines are joined with LF byte `0x0A`; CRLF is not canonical;
10. the serialized record ends with exactly one final LF byte;
11. there is no UTF-8 BOM;
12. the record is encoded as UTF-8. Because the frozen field names and the two
    constrained action fields are ASCII, their bytes are identical to ASCII;
13. Markdown fences, indentation outside the record, surrounding blank lines,
    and explanatory prose are excluded.

`resume_operation_id` is the lowercase 64-hex SHA-256 digest of exactly those
serialized bytes:

```text
resume_operation_id = sha256(canonical_resume_operation_identity_bytes)
```

Any difference in field order, value grammar, line endings, final newline,
whitespace, casing, encoding, or BOM produces a different/non-canonical record
and must fail validation.

## Completion Predicate Binding

The durable completion predicate for an automatic follow-up must bind the same
`resume_operation_id`, `resume_action_kind`, and `resume_action_key`.

A predicate that proves only that some operation of the same class happened is
insufficient when multiple concrete follow-ups are possible.

The T102 response ACK is therefore amended to include the action key:

```text
MAINTAINER_PLANNER_RESPONSE_ACK
protocol_version: agent-planner-review-v1
notification_id: github-pr-comment:<request-comment-id>
planner_decision_comment_id: <id>
exact_head: <sha>
resume_operation_id: <sha256>
resume_action_kind: <kind>
resume_action_key: <key>
status: COMPLETED
completion_evidence: <durable predicate/evidence>
```

A later Maintainer session may suppress replay only after validating both:

1. the canonical operation identity recomputes to the recorded
   `resume_operation_id`; and
2. the completion evidence proves completion of that exact action identity.

An ACK without a valid action key / canonical operation identity is not
sufficient replay suppression evidence.

## Verification Addendum

In addition to the existing T102 verification, implementation must test or
demonstrate:

- two independent derivations of the same canonical identity produce the same
  SHA-256;
- CRLF, missing final LF, extra whitespace, reordered fields, invalid action
  kind/key syntax, or uppercase/malformed exact-head encoding fail validation;
- two different `resume_action_key` values under the same notification,
  Planner decision, exact head, and action kind produce different operation
  IDs;
- two different action kinds with the same action key produce different
  operation IDs;
- when one Planner decision yields two resumable follow-ups, completion of one
  does not suppress the other;
- the existing interruption-before-completion and
  completion-before-ACK recovery cases validate the exact canonical operation
  identity before deciding whether to retry.

## Landing Requirement

Before final T102 landing, either:

1. fold this amendment into the primary T102 task/protocol document; or
2. retain it as a same-ID amendment and add it to the archive's same-ID
   amendment lookup.

Do not leave the landed repository with an undiscoverable normative amendment.
