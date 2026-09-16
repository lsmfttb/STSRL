# T092 internal Search-state telemetry implementation boundary

T092 adds one task-scoped native companion API,
`StepSimulator.battle_search_v2_with_internal_teacher_telemetry`. It is opt-in
and the existing `battle_search_v2` API remains the default-off, unchanged
Search-v2@400 path.

The companion accepts only the frozen unguided arguments `(simulations,
include_potions)`; T092 collection must pass `400, false`. It runs Search to
completion first, then traverses the final tree using private copies of the
root `BattleContext`. The replay transition count is emitted as
`telemetry_extraction_transition_count` and is never added to controller
`native_simulator_steps`. The replay does not access or mutate Search RNG,
the searched context, the tree, action ordering, or edge statistics.

Only expanded, nonterminal nodes at `tree_depth >= 1` whose input state is
`PLAYER_NORMAL` or `CARD_SELECT` are emitted. The depth-0 root is deliberately
absent from internal rows, while its normal root report remains available for
OFF/ON parity and T090/T091 reproduction. A row contains the pre-existing public tactical
projection, ordered teacher-searchable public actions, final child visits and
finite means (or null mean for zero visits), and separately reported public
actions excluded by the frozen teacher. The Python consumer rejects
checkpoint/RNG/draw-order/ActionQueue/private data recursively before it can
become candidate content. Tree depth, occurrence identity, expansion ordinal,
source/split, visits, and means remain provenance or target metadata rather
than student input.

The task-native source descends from
`20a6c2b3a9cea817c988178b814f083ff889853f`; the exact task commit, ancestry,
binary-diff hash, schema, and frozen configuration are pinned in
`docs/t092_task_scoped_native_provenance.json` before any canary. The native
report also carries a complete `t092-frozen-search-v2-teacher-config-v1`
envelope; the STSRL parser requires its exact schema, Oracle-like information
regime, 400 simulations, no-potion setting, highest-mean root rule, no policy
prior/leaf value, and rollout/terminal-utility identities. Missing or
conflicting report or task-native facts fail closed. This document does not
change the merged `docs/sts_lightspeed_source_manifest.json` pin.

Retained occurrence JSON is independently revalidated before canary evidence
is accepted. Every row carries exact
`t092-internal-search-state-occurrence-v1` / version `1` metadata and its
original `PLAYER_NORMAL` or `CARD_SELECT` input state. Exact occurrence/child/
cost field sets, task-native identity, frozen teacher envelope,
source/split/parent-decision binding, `tree_depth >= 1`, public-action scalar
types, finite supported means, zero-visit unknowns, and the recursive public
firewall all fail closed. This prevents a file-only evidence reader from
accepting injected private or malformed internal rows.

## Harnesses

`python -m sts_combat_rl.commands.t092_internal_search_state canary-select`
only writes the prescribed deterministic 12-source selection from an existing
ledger. `validate-native` only validates an already-captured native JSON report
and writes an offline summary. Neither command restores checkpoints nor runs a
simulator. The paired OFF/ON canary and the 413-start formal collection require
their separate Maintainer authorizations and are intentionally not invoked by
these harnesses.
