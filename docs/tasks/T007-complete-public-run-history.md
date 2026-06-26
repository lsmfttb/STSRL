# T007: Complete Public Run History (superseded)

## Disposition

PR #9 attempted this task and was closed without merge on 2026-06-22. Its
native patch does not apply to the canonical external patch stack, loses
checkpointed encounter history, omits persistent resource snapshots, and
combines native projection, Python schema/history, artifact migration, replay,
and audits into one unreviewable change.

This task is retained only as the historical umbrella for the intended
capability. It is not an executable task and must not receive a new branch or
pull request. Do not resume the closed branch or cherry-pick its commits.

## Replacement Tasks

The desired capability is deliberately partitioned as follows:

1. [T014: Native public projection capability](T014-native-public-projection-capability.md)
   owns the focused native capability matrix, raw public projection,
   legal-action source parity, and checkpoint fidelity.
2. [T015: Public run context and controlled history](T015-public-run-context-and-controlled-history.md)
   owns the typed Python contract plus append-only history in
   `execute_controlled_run`.
3. [T016: Public-context artifacts, replay, and audit](T016-public-context-artifacts-replay-and-audit.md)
   owns migrations, persisted propagation, portable replay comparison, and
   coverage auditing.

See [`README.md`](README.md) for current task lifecycle states and
[`../t007_review_handoff_2026-06-22.md`](../t007_review_handoff_2026-06-22.md)
for the full review evidence and closed-PR reference.

## Historical Objective

The eventual capability remains one typed, versioned, sanitized public
run-context contract containing public tactical state, persistent resources,
typed visible history, complete visible map/routes, and the visible Act Boss.
It must never receive hidden RNG, unrevealed future encounters, hidden draw
order, raw checkpoints, simulator internals, or the hidden Act-3 second Boss.

The three replacement specifications, not this cancelled umbrella, are the
authoritative acceptance contracts.
