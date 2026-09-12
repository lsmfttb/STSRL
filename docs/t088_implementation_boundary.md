# T088 implementation boundary

This is implementation evidence for the approved task at
`b31162fa8df84a02ea45555e6e65055bed986494`, not a task-contract amendment or
an execution authorization. T088 remains incomplete.

The STSRL-side implementation provides the exact H1 component calculation,
the `beam_h1_w32_b400_v1` controller over native checkpoint/restore/step, and a
four-arm construction surface. A/B construct the accepted
`T085UnguidedBattleSearchV2Controller` unchanged with 100/400 simulations. C
counts each hypothetical `adapter.step` application once, restores the root
even on errors, and keeps ordered action indices including duplicate ids.
D constructs only `progressive_bias_mcts_h1_400_v1`, pinned to canonical native
`20a6c2b3a9cea817c988178b814f083ff889853f`. It supplies no Python prior/value
callback or root prior, validates required root/counter/H1/audit output fail
closed, and retains the native work and progressive-bias telemetry.

The controller unit tests use abstract labelled graphs only. They are not
T087 cohort substitutes, simulator evidence, canary records, or a formal run.
The source manifest is updated only to that accepted canonical native
descendant and declares its minimal opt-in capability. No retained cohort,
terminal diagnostic formula, native repository, or learned input has changed.

## Native surface required before Arm D

Read-only inspection originally used native Git object
`96052d24b9c2c16ff25b6f7241edd972613be997`. Its governed, canonical descendant
`20a6c2b3a9cea817c988178b814f083ff889853f` in
`lsmfttb/sts_lightspeed`. The relevant owners are:

- `include/sim/search/BattleScumSearcher2.h`: the tree `Node`/`Edge` state,
  policy-prior and leaf-value callbacks, counters, and search methods;
- `src/sim/search/BattleScumSearcher2.cpp`: `enumerateActionsForNode`,
  `evaluateEdge`, `step`, `playoutRandom`, and `updateFromPlayout`;
- `bindings/slaythespire.cpp`: the `StepSimulator.battle_search_v2` binding and
  returned root/tree telemetry.

The former bound API had no all-node child-state progressive-bias hook. Its existing
policy callback is normalized into priors and multiplied by a parent-visit
factor; it cannot express the required signed `0.50 * H1 / (1+n)` term.
Its leaf-value callback replaces the required native terminal continuation.
The existing internal-leaf continuation interface requires a separate action
seed and cannot reproduce a single native searcher's random-rollout stream.
These are not valid substitutes for Arm D.

The landed governed native delta is:

1. Add an opt-in search surface with child H1 components/availability on the
   searchable tree edges. Obtain each required hypothetical child through the
   native copied Battle context/action transition. Restrict H1 reads to the
   approved HP, block, turn, and targetable-enemy fields; count any additional
   transition used to obtain that child.
2. Preserve the existing `evaluateEdge` exploitation/exploration calculation
   and add exactly `0.50 * child_h1 / (1 + child_visit_count)` wherever the
   nonterminal child heuristic is available. No H1 input or extra child
   evaluation is enabled for A/B. Preserve native random leaf selection,
   `playoutRandom`, `evaluateEndState`, backup, and root statistics.
3. Expose an explicit opt-in binding and bounded audit telemetry containing
   parent depth, child H1 components, child visit count, unmodified base score,
   bias contribution, and resulting score. Tests must prove depth > 0 use,
   decay, A/B zero contribution, and zero-bias recovery of the base term.
4. Retain `actionExecutionCount`/`native_simulator_steps` and add direct rollout
   and terminal-utility evaluation counters where those counts are applicable.
   Expose all heuristic successor work rather than treating 400 simulations as
   400 transitions. The existing `expandedNodeCount` already counts search
   expansions separately from random rollout enumeration.

The base exploitation term uses `evaluationSum / (simulationCount+1)` divided
by `bestActionValue-minActionValue` when a best action sequence exists; the
exploration term is `3*sqrt(2) * sqrt(log(parentVisits+1)/(childVisits+1))`.
Its current zero-range behavior must not be silently repaired during this
extension. The task requires the frozen term or a separately approved material
amendment before canary.

This delta touched native search semantics and therefore required a temporary
`work/T088-*` branch from the verified base, independent native semantic review,
canonical `stsrl/main` landing, ancestry proof, and an explicitly accepted
STSRL pin update. The native lane has landed canonically; this worktree makes no
native edit and binds only that exact resulting identity.

The repository-side workflow now has a deliberately non-executing evidence
surface in `sim/t088_tournament_workflow.py`. It validates the exact 413-record
T087 A/B/C membership and order, produces the 413 x 4 arm plan with
`execution_authorized: false`, and rejects partial/duplicate/substituted formal
rows. It also makes the bounded canary selection deterministic from explicit
T087 facts, validates no learned-model calls and retained work facts, computes
the fixed 20,000-resample paired statistics, creates the separately retained
blind bundle/provenance map, and validates report/retention identity shapes.
The module does not import a simulator adapter or invoke a controller: a future
authorized runner must supply actual restore/execution evidence to it.

This is implementation readiness only and must be independently reviewed before
a Maintainer can authorize a canary. No canary, formal tournament, baseline
promotion, or downstream Non-Combat execution is enabled by this partial
implementation.

## Local verification

The existing `/home/lsmft/stsrl-spikes/py313-torch/bin/python` environment ran
the controller/T085/T087/task-document tests in the preceding implementation
slice (136 passed), plus the independent non-simulator
`test_t088_tournament_workflow.py` checks. Ruff check/format and compileall
pass on the added workflow files. System Python itself has no pytest or Ruff
installation; no dependencies were installed. No native extension, canary,
formal cohort, or large simulator job was executed for these checks.
