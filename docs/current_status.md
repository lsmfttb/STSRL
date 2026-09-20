# Current Status

Last updated: 2026-09-20.

This is the compact, merge-stable projection of the accepted project state on
`main`. It answers what is true now; it does not narrate a PR's approval or
merge phase. Task contracts and retained reports contain the detailed evidence
behind each conclusion.

## Goal and information boundary

STSRL targets an A20 Heart victory. The trainable scope is Battle decisions;
Non-Combat decisions remain a separately named driver. The real Slay the Spire
game is the mechanics and live-runtime authority. Large-scale training,
restored evaluation, native Search, and simulator gates use the pinned
`sts_lightspeed` integration. Normal-information controllers receive only
player-visible run context; Oracle-like or full-simulator continuation is
explicitly labeled and is not a normal-information claim.

The live-game path uses the CommunicationMod runtime adapter and the shared
public decision/action contract. `execute_controlled_run` remains the
authoritative complete-run advancement path. Battle and Non-Combat controllers,
their distributions, labels, and evaluation reports remain separate.

## Accepted runtime and native baseline

- The canonical native source is
  `lsmfttb/sts_lightspeed`, `refs/heads/stsrl/main`, at
  `97f59b620efe5ee1571f8da298c99d1e21c1149b`.
- T097 accepted the reproducible native public-information capability at pin
  `d309170198e21e57041a84dcfdbc255cdda4052e`; T099 advanced the source pin
  after proving the old pin and reviewed native PR #20 lineage.
- T099 accepted the native particle/Search bridge capability. Its outer
  particle distribution is public-consistent; each continuation is
  `full_simulator_state_oracle_like`; returned values are a
  `full_state_continuation_strategy_fusion_proxy`. It does not perform
  cross-particle aggregation or action selection and does not claim an exact
  public Q value, exact posterior, or normal-information-optimal Search.
- CommunicationMod formatting remains centralized in
  `src/sts_combat_rl/comm/protocol.py`; CLI modules route to command workflows.

## Strongest accepted Battle and Non-Combat results

T088 freezes unguided Search v2 at 400 simulations as the strongest accepted
non-learned Battle baseline on the exact matched Battle-start cohort. Search
v2 at 100 remains a historical comparator. Beam weighted-best-first and
progressive-bias MCTS are not promoted. This is a simulator-side Battle
baseline, not a complete-run A20 or live-game dominance claim. See
[`T088`](tasks/T088-classical-combat-search-baseline-tournament.md).

T085's corrected value-search comparison accepted
`CORRECTED_VALUE_SEARCH_HARM_CONFIRMED` for its bounded Search claim. It did
not establish complete-run or Non-Combat improvement. See
[`T085`](tasks/T085-corrected-leaf-value-search-repair.md).

T089's fresh matched evaluation did not establish learned Non-Combat
improvement. No learned Non-Combat promotion or T066 continuation follows from
that result. See
[`T089`](tasks/T089-frozen-search-self-generated-non-combat-policy.md).

## Current data-surface diagnosis

The following accepted results describe the current evidence boundary without
claiming a student, controller, or Search promotion:

- T090: `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT`; the frozen complete-root
  utility target surface was too sparse for its preregistered gate, so training
  and held-out evaluation were not run.
- T091: `ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED`; partial root support
  was denser but failed its coverage, supported/legal, and action-kind gates.
- T092: `INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH`; retained internal occurrences
  support a future read-only telemetry companion, without changing Search.
- T093: `INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT`; leakage-safe
  source-start diversity failed the frozen A-cell minima, so no training or
  integration was run.
- T094: `A_COHORT_CANONICALIZATION_LIMITING`; A-cohort attrition after exact
  cross-split exclusion and canonical ownership is the accepted diagnosis.
- T095: `EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE`; the primary repeated-public-
  state aggregation surface had no support at `k_min=8`.

These outcomes do not establish that Battle learning or hidden-future averaging
is impossible. They identify the measured data and provenance boundaries. The
task contracts retain the exact cohorts, thresholds, hashes, and artifact
locations.

## Public-information and particle boundary

T096's native pilot established public projection/legal-action parity and the
ordinary hidden-draw distribution surface, but classified draw-knowledge and
hidden-intent mechanics as `NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`.
T097 then accepted the reproducible native capability input.

T098's bounded re-entry accepted representative ordinary, known-top, Frozen Eye,
and supported hidden-intent witnesses as
`PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`, with timing-mixed unsupported
behavior failing closed. It did not claim particle sufficiency, arbitrary-state
support, exact posterior correctness, Search improvement, or T034 completion.

T099 accepted the native particle/Search bridge and its occurrence-equivalence
mapping, public/legal-action parity, sanitized rows, audit counters, and
fail-closed unsupported/ambiguous mappings. It remains a capability input, not
a convergence result. T034 remains `BLOCKED` in the task archive while the
broader native public-consistent hidden-future boundary is unresolved.

## Active scientific boundary

The next possible scientific successor is T101, a separately specified bounded
particle-count convergence task. T100's repository-maintenance work does not
publish, authorize, or pre-specify that experiment. T063 and T066 remain draft
directions; no task is promoted merely by appearing in a document or Planner
Issue.

The retained closed-route conclusions remain available through the task archive
and contracts, including the earlier Oracle-guided Search, later-act reach,
root-prior allocation, curriculum, value-target, and Non-Combat investigations.
They are summarized here only to preserve current boundaries:

- Oracle assistance validated plumbing but did not establish controller
  improvement.
- Search-guidance and root-prior routes did not establish a promoted learned or
  allocation controller.
- T064's exposure-order curriculum did not pass the frozen transfer gates.
- T065's source selection ended as a valid leakage/duplicate diagnostic rather
  than a policy result.
- T079--T084 repaired and audited value-target semantics and produced qualified
  internal-leaf target data; T085 measured bounded value-search harm.

## Durable information layout

The repository uses four distinct information surfaces:

1. The [Planner Operating Dashboard issue #107](https://github.com/lsmfttb/STSRL/issues/107)
   is the concise operating/startup card.
2. Planner research ledger issue [#85](https://github.com/lsmfttb/STSRL/issues/85)
   is low-friction research memory for hypotheses, direction changes, route
   closure, and cross-session context.
3. The active task contract and exact PR are the execution transaction; the PR
   carries exact-head approvals and lifecycle events.
4. This current-state document, architecture/governance documents, task
   archive, task contracts, experiment records, and Git history provide durable
   project truth and retained provenance.

Issues do not authorize implementation, and history does not override current
durable contracts. Future task-specific support files belong under
`docs/tasks/support/Txxx/` when a stable repository path is needed. Existing
root-level documents remain valid legacy paths and were not mass-migrated.

## Evidence and limitations

Large generated artifacts remain outside Git under stable ignored paths with
schema, provenance, hashes, sizes, regeneration commands, compatibility, and
retention information recorded by their task. Current status records only the
durable identity and conclusion needed for safe navigation; it is not a second
artifact database.

No current result claims A20 Heart completion, universal Battle dominance,
normal-information-optimal Search, exact posterior inference, broad learned
controller improvement, or live-game deployment quality beyond the explicitly
accepted runtime adapter contract.
