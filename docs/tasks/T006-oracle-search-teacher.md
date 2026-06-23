# T006: Oracle Search Teacher Pipeline

Status: `READY`.

## Objective

Expose the simulator-native hidden-state battle search as an explicitly
Oracle-like controller and teacher-data pipeline, then compare named search
budgets and root-selection rules on immutable T005 cohorts.

This task supplies an engineering upper-bound and diagnostic teacher. It does
not establish a normal-information controller or a claim about real-game
strength.

## Current Main Baseline

T003 provides versioned decision artifacts, occurrence-disambiguated legal
action identities, and immutable controller provenance. T004 provides
portable natural battle-start records with source checkpoint identity,
sampling component, and fresh-adapter replay restore. T005 provides
versioned fixed cohorts and per-battle reports containing controller
provenance, information regime, simulator steps, wall-clock time, and an
explicit controller-compute telemetry field.

T017 replaced the former day-to-day patch-stack workflow with a pinned
external source integration. The existing native code contains search sources
but does not yet expose root statistics or a repository `OnlineController` for
them. Current portable records preserve explicit public-context status; teacher
rows must retain that status rather than implying complete public history.

## Dependencies

- T003, T004, T005, and T017 are complete.

## Scope

- Add the smallest focused `sts_lightspeed` source surface needed to invoke
  the native `BattleScumSearcher2` from a restored battle and obtain one root
  row for every legal root action. Extend the T017-managed pinned source
  integration and manifest; do not append another ad hoc patch to the retired
  ordered patch-stack workflow.
- Implement a versioned `OracleSearchController` that satisfies
  `OnlineController`, is explicitly allowed to copy/use simulator state, and
  returns a currently eligible legal-action index by occurrence-disambiguated
  root-action identity. It must fail closed when native root rows cannot be
  mapped one-to-one to the current legal action list.
- Give the controller `ControllerProvenance.kind="oracle_battle_search"` and
  record, at minimum, `information_regime="full_simulator_state_oracle_like"`,
  native-search API/patch identity, search budget, rollout/leaf configuration,
  root-selection rule, action-space configuration, seed/reproducibility
  settings, and every search behavior-changing option.
- Preserve distinct fields for: (1) the direct teacher action chosen by the
  configured root-selection rule, (2) a soft root-visit target, and (3) the
  behavior action actually taken when a DAgger-style collection loop is used.
  A record may omit a behavior action when none was executed, but it must never
  substitute it for the teacher action.
- Define a current-schema Oracle-teacher JSONL artifact. Each row must retain
  the source checkpoint identity, source distribution and sampling component,
  pre-decision occurrence-safe legal actions, root statistics, teacher target,
  controller/search provenance, and explicit public-context availability. Use
  the established sequential artifact-migration framework; do not overload a
  policy decision record with ambiguously named search fields.
- Add focused command workflows below `src/sts_combat_rl/commands/` for
  collecting teacher rows from a portable pool and evaluating a named
  Oracle-search controller on an existing, immutable fixed cohort. CLI code
  may parse and route only.
- Fixed evaluation must load the supplied cohort unchanged. It must not select
  a new cohort while comparing search budgets or `highest_mean` with a
  visit-based diagnostic rule.
- Record and report root visits, root means/values, simulations, native
  simulator steps, controller model calls when applicable, wall-clock time,
  unmapped root rows, and failures. Missing telemetry is explicit, never zero.

## Out Of Scope

- Reporting Oracle-like results as normal-information performance or as a
  real-game result.
- Normal belief search, public-consistent hidden-future sampling, restart/SL
  search, broad neural training, or continuation-value modeling.
- Directly cloning a known-hidden-future Oracle action as a promoted normal
  policy.
- Modifying T004 pool writers, creating public run history, or fabricating
  simulator actions in Python.

## Design Constraints

- The final game is the mechanism authority. `sts_lightspeed` is the current
  large-scale simulation substrate; every result and native-source report must
  name its external source identity.
- All controller, dataset, and evaluation outputs use exactly
  `full_simulator_state_oracle_like`. No normal-public artifact may silently
  consume native hidden state.
- `highest_mean` is the default direct root selection. Visits are retained for
  diagnostics and optional soft targets; a visit-based selected action must be
  explicitly named and reported separately.
- Root rows are matched through the current legal action identities, including
  duplicate occurrence. Index-only matching, label-only matching, and an
  arbitrary fallback action are forbidden.
- Teacher collection retains source sampling weight separately from unique
  source coverage. Repeating one checkpoint changes training weight only.
- Every fixed-cohort comparison uses the same saved cohort identity, action
  space, maximum battle steps, and source provenance. Truncation, restore
  failure, illegal selection, root-mapping failure, or simulator error makes
  an evaluation unsuccessful.

## Deliverables

- Focused reproducible native-search source changes and adapter exposure with
  the T017-managed source verification check.
- `OracleSearchController`, root-statistics mapping/validation, provenance,
  telemetry, and unit tests.
- Versioned Oracle-teacher artifact, reader/writer/migration path, collector,
  and tests separating teacher, visit, and behavior fields.
- Fixed-cohort loading/evaluation workflow for Oracle controllers, plus a thin
  CLI route and report formatter.
- WSL teacher-collection and fixed-cohort comparison gates.

## Acceptance Criteria

- Every selected Oracle action is a unique currently eligible legal action, or
  the decision fails closed with a named root-mapping problem.
- Controller provenance, teacher rows, and fixed-evaluation reports all carry
  `full_simulator_state_oracle_like` and the complete named search
  configuration.
- Teacher action, soft visit target, and behavior action remain separately
  inspectable after serialization and migration.
- Repeating a deterministic source/checkpoint/search configuration yields the
  same non-timing root statistics and teacher target; all stochastic settings
  are named in provenance.
- `highest_mean` and any visit-based diagnostic selection are evaluated on the
  same immutable cohort and cannot be confused in a report.
- Reports include simulations, simulator steps, wall-clock time, root rows,
  controller telemetry, source checkpoint provenance, and every failure.
- The T017-managed source integration builds cleanly and the required
  local/WSL checks pass.

## Required Verification

Run the standard local gates from `tasks/README.md`, focused root-mapping,
artifact, controller, and cohort-loading tests, and:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-oracle-search-teacher /tmp/t006-pool.jsonl --oracle-teacher-output /tmp/t006-teacher.jsonl --oracle-search-simulations 20 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-oracle-fixed-evaluation /tmp/t006-cohort.jsonl --oracle-search-simulations 20 --oracle-root-selection highest_mean --sim-ascension 20 --sim-steps 200 --log-file -"
```

The PR must first create `/tmp/t006-pool.jsonl` and freeze
`/tmp/t006-cohort.jsonl` using the current T004/T005 workflows. The new
commands must fail nonzero on invalid artifacts, a cohort restore mismatch,
root-action ambiguity, illegal selection, truncation, or evaluation error.
The report must name the exact external simulator source identity.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_battle_search_teacher.patch
patches/sts_lightspeed_battle_search_root_actions.patch
src/sts_combat_rl/sim/search_policy.py
src/sts_combat_rl/sim/search_selection.py
src/sts_combat_rl/sim/search_teacher.py
src/sts_combat_rl/sim/expert_iteration.py
tests/test_search_policy.py
tests/test_search_teacher.py
tests/test_expert_iteration.py
```

The legacy implementation predates the current cohort/provenance boundary. It
may be consulted selectively but is not an acceptance reference and must not
be cherry-picked wholesale.

## PR Report

Include task ID, external simulator source identity, native API inventory,
teacher artifact schema and migration behavior, source pool/cohort identities,
all controller and information-regime provenance, both root-selection results,
root-mapping/telemetry failures, exact local/WSL results, legacy files
consulted, known limitations, and every unmet acceptance criterion.
