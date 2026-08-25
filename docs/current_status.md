# Current Status

Last reviewed: 2026-08-26.

This document is the main maintainer's canonical execution-result report for
the planner and describes the latest `main` branch only. Results from local
artifacts, old branches, or unmerged pull requests do not count as implemented
capabilities. It reports accepted behavior, evidence, limitations, and
blockers; it does not itself propose or authorize a successor task.

## Current Goal

Build the foundations for an A20 battle agent. Search remains the intended
primary battle policy, and learned policies or values are expected to guide or
accelerate search. Non-combat decisions remain outside the trainable agent.

The task index lists the canonical lifecycle state for the published backlog.
The M1 model-guided Oracle search sandbox is complete through synthesis. It
validated Oracle-like search plumbing but did not demonstrate controller
improvement. The first post-M1 coverage refresh, T031, is also complete and
showed that the current A20 source distribution is still Act-1-only. T036 is
complete and added search-controlled reachability tooling, but its accepted
10-run A20 smoke arms were also Act 1 only. T037 is complete and recovered the
historical Boss/Act2 source signal at 1,000 terminal runs. T039 is complete and
records the accepted T037 source-coverage contract in
`docs/a20_later_act_boss_source_coverage_contract.md`. T032 is complete: it
ran the narrow teacher/checkpoint diagnostic refresh over the accepted T039
contract, produced a `narrow_curriculum` checkpoint and calibration evidence,
and kept broad A20 training readiness closed. T035 is complete: it added a
versioned deeper model-guided Oracle-like search comparison using refreshed
diagnostic checkpoint provenance, but the accepted smoke evidence tied the
baseline and T028 outcomes rather than demonstrating improvement. The upstream
assisted source-generation batch is now complete: T040, T041, T042, T033,
T043, and T044 are all merged. T044 did not show model-guided search
improvement over baseline. T045 is complete: it added the offline
`post-t044-failure-analysis-report-v1` workflow, classified the accepted T044
failure evidence, and recommended native root-prior allocation as the primary
next search path. T046 is complete: it added the minimal native root-prior
allocation surface and smoke report workflow. T047 is complete: it added the
root-prior guided Oracle-like comparison workflow and produced the first
matched smoke showing root-prior guided search beating both baseline and
post-search guidance on one current pinned T046-compatible restored start.
T048 is complete: it scaled that comparison to two non-trivial matched fixed
cohorts and again found root-prior guided search ahead of both baseline Oracle
search and post-search guidance at equal native root budget. T049 is complete:
it added checkpoint-guided complete-run source collection for the same three
search arms and accepted a bounded A20 smoke that found no Boss or later-act
reachability. T050 is complete: it added source-pool shard merge/finalization,
ran the 50-terminal-run-per-arm complete-run scale pass, reached an Act-1 Boss
only in the baseline and post-search arms, and reached no later-act starts in
any arm. T051 is complete: it ran the 1,000-terminal-run-per-arm matched
source collection, recovered a small Act-2+ signal in the post-search and
root-prior guided arms, and kept broad training closed. T052 is complete: it
built the 93-record T051 Boss/later-act fixed diagnostic cohort and found
root-prior guided search regressed by one win overall and on the five-record
Act-2+ subset while tying the Boss-only subset. T053 is complete: it added the
offline root-prior allocation failure analysis over the T052 disagreement
records, found four root-prior disagreement records, and recommended a
guardrailed root-prior allocation repair experiment. T054 is complete: it
added the versioned guardrailed root-prior variant, repaired the T052 overall
and Boss-only regression against the existing root-prior arm, tied baseline
and post-search overall, and left the five-record Act-2+ limitation unresolved.
T055 is complete: it scale-validated the repaired variant on the retained T048
fixed cohorts, found the guardrail tied existing root-prior on the current
8-record cohort but regressed by one win on the assist_0 21-record cohort and
on the labeled aggregate, and recommended abandoning the guardrail path. T056
is complete: it synthesized the retained T048/T050/T051/T052/T053/T054/T055
evidence, closed the T054/T055 guardrail branch, and selected exactly one
non-guardrail next path: an existing-root-prior allocation/telemetry
diagnostic. T057 is complete: it added that offline diagnostic, summarized 122
retained existing-root-prior records and 2087 existing-root-prior decisions,
found exact all-arm step-level selected-action comparison unavailable for every
retained record, and selected exactly one next path: a root-prior
selected-action telemetry instrumentation or replay diagnostic. T058 is
complete: it made selected-action comparison available for all 122 retained
T048/T052 records, found first selected-action divergence against baseline and
post-search on all 122 records, identified 2 harmful selected-action divergence
records, and selected exactly one next path: a bounded root-prior allocation
repair experiment. T059 completed that experiment: entropy-tempered root-prior
allocation preserved the T048 positive result but tied the existing root-prior
arm on the T052 and T053 harmful subsets. Allocation repair is closed; it does
not authorize root-prior reachability, promotion, or further allocation
variants. T060 was cancelled before execution because a 10,000-run scale-up of
the unchanged profile would not diagnose the reachability-policy bottleneck.
T061 is complete. Its matched restored-battle curve and six-arm complete-run
factorial probe found a positive battle-budget effect on Act-2 entry under
`expert_non_combat_v1`, no Act-3/Act-4/Heart reachability, and selected T062 as
the single next task. T062 is complete through its accepted
calibration-infeasibility early exit. T067 is complete: its exact public-node
cache preserved semantics but recorded no reuse, left two guided arms
minimum-budget wall-clock infeasible, and selected T068 without authorizing an
outcome comparison. T068 is complete: every guided arm exposed only
synchronous singleton callbacks, so native-boundary batching, calibration, and
outcome comparison remained closed; measured public-feature encoding cost
selected T069. T069 is complete: its exact search-scope public-context
projection preserved accepted semantics, passed every material-improvement
gate, and locked all wall-clock and simulator-step calibration arms. T069 ran
no 93-record outcome aggregation. T070 is complete: it integrated the accepted
native tree-geometry companion, ran all ten frozen 93-record primary stages and
all six frozen 16-record high-budget stages, rejected Search v2 promotion, and
selected Case C. The 100-simulation budget is descriptively insufficient, but
the high-budget guidance signal is false. T070 recommends T064 to the planner
without publishing it. T064 is now complete with a valid negative Case B. It
selected 460 leakage-free, duplicate-free restored starts, trained the frozen
static and assistance-annealed arms for seeds 64001/64002, and completed both
frozen T044 cohorts and the 93-record T052/T070 comparison. The curriculum arm
tied static on T044 model-guided wins (46 at `assist_hp50`, 18 at `assist_0`),
but lost one T052 win at seed 64002 and on the Act-2+ subset. Only three of six
transfer gates passed, so no curriculum promotion or natural scale-up is
authorized. The terminal decision recommends T065 to the planner; it does not
publish or authorize T065. There are currently no `READY` tasks. T034 remains
blocked on native public-consistent hidden-future sampler support. T071 is now
complete after PR #70 merged at `dce372b`; it reduced T064-specific validation
duplication, established T044 validation ownership, and added the detached
long-job/status and stage/run-local reuse conventions. No T064 scientific rerun
was required, and T065 remains `DRAFT`.
T072 is now complete after PR #71 merged at `98de21b`. It retired the closed
T053–T059 task-specific simulation/command/test executors and their CLI and
lightspeed routing, while preserving the generic root-prior/native-search and
T052 retention surfaces. Its 21-file deletion passed the required size gate
with 19,916 fewer tracked `src`/`tests` Python lines. T072 changed no accepted
artifact schema or scientific result, and its historical task records point to
the frozen pre-retirement source anchor. No simulator, training, or evaluation
rerun was required. T065 remains `DRAFT`.
T073 is now complete after PR #72 merged at
`dac26774f7cc70abae6be1693772418398e1e7eb`. It removed the completed T064 and
T067--T070 executor command modules, scripts, and executor-only tests; moved
live source-identity, sharding, search-cost, and feature-identity helpers to
neutral owners; and preserved the accepted T064/T067/T069 schema identifiers
and T070 schema-contract blob. The frozen-baseline inventory found no targeted
T064/T067/T068/T069/T070 CLI routes, so no maintained T062 or generic Search v2
route was removed. The final Git-object gate reduced tracked Python by 16,854
lines across `src` and `tests`, including 9,634 lines under `src`; the final
local suite passed 729 tests. No simulator, training, evaluation, or scientific
artifact rerun was required. The merge does not authorize or publish T065:
the Planner must first perform the fresh repository-wide quality review
required by T073, and T065 remains `DRAFT`.
T074 is now complete after PR #73 merged at
`7c2dcf5d8a6d74bb03e7fda173000dad006933ce`. It repaired the forward
`controlled_run -> policy -> batching -> controlled_run` boundary by extracting
the neutral policy contract, moving batch evaluation and non-combat drivers to
explicit owners, and reducing `sts_combat_rl.sim.__all__` from 336 to 31
foundational names. The combined policy surface decreased from 1,494 to 1,466
physical Python lines and `sim/__init__.py` from 760 to 89. The independent
final-head suite passed 730 tests plus the focused boundary gates, compileall,
ruff, format, and combat/non-combat mocks; fixed-seed actions, reasons, and
provenance matched the exact pre-T074 baseline. No simulator, training,
evaluation, artifact-schema, checkpoint, or scientific-result rerun was
required. T065 remains `DRAFT`; the required post-T074 Planner review must
reassess the deferred CLI, fixture, CI/open-source, and large-module findings
before any feature task is published.

## Implemented On Main

### Runtime

- CommunicationMod-style stdin/stdout probe with protocol output isolated from
  logs.
- T019 mechanical CLI refactor. `src/sts_combat_rl/cli.py` is now a thin
  entrypoint for parser construction, top-level validation, logging/capture
  setup, PyTorch training dispatch, `sts_lightspeed` command dispatch, mock
  handling, and stdin protocol mode. Parser construction, CLI validation,
  timestamped path helpers, simulator policy builders, and lightspeed routing
  live in focused modules under `src/sts_combat_rl/commands/`. The broad
  `sts_combat_rl.sim` export surface is explicitly audited by regression tests
  rather than silently growing.
- T074 core decision/policy boundary repair. The low-level contract is now
  framework-neutral and acyclic, offline batch evaluation and versioned
  stochastic/expert non-combat drivers have explicit ownership, and the
  package-level simulator surface is limited to 31 documented foundational
  names. Existing controller, CLI, simulator, provenance, and artifact
  contracts remain unchanged.
- Live CommunicationMod runtime entry point that consumes one JSON observation,
  exposes only the sanitized public tactical contract to an `OnlineController`,
  emits at most one protocol command, and fails closed on unsupported or
  incomplete battle decisions.
- Framework-neutral simulator contracts and a Python adapter for the pinned
  external `sts_lightspeed` source integration.
- Real simulator execution is documented and performed through WSL.
- Versioned external `sts_lightspeed` source manifest
  (`docs/sts_lightspeed_source_manifest.json`) and canonical source verifier
  (`scripts/verify_lightspeed_source.sh`). The manifest pins upstream
  `gamerpuppy/sts_lightspeed` base commit
  `7476a81954020087da31d41d16fddf475746ec2d` and the active fork integration
  branch `refs/heads/stsrl/main` at commit
  `fee272f1ae21c283ad2161f55293cfe6d714134a`. The supported capability set
  includes the opt-in `native_battle_search_v2_tree_geometry` companion API;
  the existing Search v2 method remains unchanged. Historical task-shaped fork
  branches are retained only as provenance, and the old ordered patch stack is
  retained only as retired provenance.

### Execution And Maintenance

- T071 post-T064 execution simplification is merged on `main` (PR #70). The
  T044-owned report surface now provides reusable controller-semantic and
  checkpoint validation, while T064 retains its strict artifact, provenance,
  order/linkage, completion, deterministic-plan, and reuse-boundary checks.
- T072 closed executor cleanup is merged on `main` (PR #71). The seven closed
  T053–T059 task-specific simulation modules, command modules, and tests were
  deleted, along with their CLI/parser/validation/lightspeed routes. Generic
  root-prior/search behavior and T052 retention-manifest support remain
  available; historical task documents and scientific conclusions are
  unchanged.
- `scripts/run_detached_job.py` provides a small disposable status contract
  with PID, command/cwd, logs, terminal state, exit code, and coarse ETA. Healthy
  long jobs are reported once and rechecked after the expected window rather
  than continuously monitored.
- T071 produced no scientific result artifact and did not rerun T064,
  `sts_lightspeed`, teacher/training, or fixed-cohort evaluation. T065 remains
  a draft planner task.
- T072 produced no scientific result artifact and did not rerun
  `sts_lightspeed`, training, or evaluation. Its accepted maintenance evidence
  is the 21-file deletion audit, the 19,916-line size reduction, and the local
  regression gates; T065 remains a draft planner task.
- T073 produced no scientific result artifact and did not rerun
  `sts_lightspeed`, training, or evaluation. Its accepted maintenance evidence
  is the T064/T067--T070 executor deletion audit, neutral ownership inventory,
  exact T070 schema-contract retention, 16,854-line `src`/`tests` reduction,
  729-test final-head suite, and the post-merge Planner quality-review gate.
  T065 remains a draft planner task.
- T074 produced no scientific result artifact and did not rerun
  `sts_lightspeed`, training, evaluation, or simulator-scale gates. Its
  accepted maintenance evidence is the acyclic policy dependency guard, 31-name
  public-surface audit, 1,494-to-1,466 combined policy-boundary line-count
  reduction, 88.3% `sim/__init__.py` reduction, 730-test final-head suite,
  fixed-seed provenance parity, and default-import PyTorch isolation. The
  post-T074 Planner quality-review gate remains active, and T065 remains a
  draft planner task.

### Battle-Agent Data Spike

- Separate battle-policy and non-combat-driver selection during bounded
  simulator rollouts.
- Explicit online-controller contract with immutable, serializable provenance.
- `execute_controlled_run` as the authoritative complete-run advancement path
  for current complete-run workflows.
- Routed battle/non-combat controllers with separately inspectable child
  provenance and composite reproducibility propagation.
- Versioned `public-tactical-v2` structured state/action contract with a
  compatibility numeric view. It carries visible hand, discard, and exhaust
  members; monster identity, canonical intent category, and simulator current
  move; player powers; potion identities; and relic identities with counters.
  Simulator-only or live-missing fields remain explicit in the parity report.
- Battle-only decision batches and contiguous battle-segment reports.
- Candidate reward components, a draft scalar reward report, and reward-labeled
  battle examples.
- Framework-neutral trainer-input JSONL round trip, model-input packing, and
  deterministic action-score contract checks.
- Offline trainer-input preflight for exported trainer JSONL artifacts. It
  validates current-schema loading, model-input packing, context rebuild,
  deterministic scoring shape, and the T009 broad-training gate without
  importing PyTorch.
- Versioned trainer-input artifact migration, complete decision provenance,
  and occurrence-disambiguated portable action identities.
- Versioned seeded stochastic non-combat driver with screen-level relative
  weights, non-combat potion eligibility, conditional-reachability tests, and
  natural A20 coverage/provenance calibration.
- Native, process-local simulator checkpoints and portable battle-start pool
  manifests. Fresh adapters restore portable records by replaying the source
  seed and occurrence-disambiguated action trace; opaque native state is never
  serialized.
- Versioned raw native public projection capability
  (`native-public-projection-v1`) on `StepSimulator`, with a diagnostic
  capability report and audit gate. It reports current screen identity,
  candidate actions from `StepSimulator::legalActions`, and currently audited
  persistent resources with native source counts. Visible Act Boss, complete
  map/routes, current node, and screen-specific payloads remain explicit
  capability gaps. The raw projection is not a sanitized controller input.
- Versioned sanitized in-memory public run context
  (`public-run-context-v1`) and ordered public history entries
  (`public-run-history-entry-v1`) are attached to controlled-run and live
  `DecisionContext` construction. `execute_controlled_run` appends one
  contiguous typed history entry after each successful visible transition,
  rejects malformed raw native projections before controller use, and exposes
  the stable in-memory context/history contract used by current artifacts.
- Current public-context artifact propagation and audit. Battle-start pools,
  fixed cohorts, fixed evaluation reports, battle decisions, trainer inputs,
  and model inputs preserve public-context status, sanitized public run
  context, and explicit context-loss provenance. Portable replay compares
  reconstructed public context, and the WSL-facing public-context audit checks
  schema validity, forbidden hidden fields, candidate parity, replay
  mismatches, and coverage.
- Seeded structural resampling of natural battle starts, with source identity,
  sampling component, structural coverage, and completed battle outcomes kept
  separate from repeated sample weight.
- Versioned fixed structural cohorts selected without replacement from portable
  natural battle-start pools, plus fresh-adapter restored-battle evaluation.
  Reports retain per-battle provenance and failures, controller telemetry, and
  separate natural-weighted, encounter-macro, room-type-macro, and
  per-stratum aggregates.
- Versioned constructed A20 battle-start supplements
  (`constructed-battle-start-v1`) with a seeded conservative transform policy
  (`constructed-battle-start-policy-v1`). Constructed rows retain immutable
  natural source identity, source checkpoint provenance, complete source public
  context/status, eligibility, proposal, requested and actual authoritative
  changes, native-support status, and separate resulting distribution tags.
  Supported T008 transforms are bounded current-HP additions, native
  simulator-sampled potion additions, and legal same-ascension ordinary/elite
  encounter alternatives through `StepSimulator.rebuild_battle_start` and
  `StepSimulator.legal_battle_start_encounters`. First-battle, cap,
  same-ascension, and visible-Boss constraints fail closed; unsupported or
  no-op proposals remain audit rows rather than constructed training rows.
- Explicitly Oracle-like native battle search teacher pipeline. The pinned
  `sts_lightspeed` source exposes `StepSimulator.battle_search`; the
  `OracleSearchController`, teacher JSONL artifact, and same-cohort Oracle
  fixed evaluation all declare `full_simulator_state_oracle_like`, retain
  occurrence-safe legal-action identities, keep teacher action and soft visit
  target separate, and compare `highest_mean` with a `most_visits` diagnostic
  on immutable T005 cohorts. This is diagnostic upper-bound/search-teacher
  infrastructure only, not normal-information or live-game performance.
- Versioned structured battle resource outcomes. Current battle-start pools,
  battle segments, reward labels, trainer inputs, and fixed-evaluation reports
  carry `structured-battle-outcome-v1` status/payload fields with sequential
  migrations for historical artifacts. Successful terminal records require an
  authoritative terminal battle outcome; missing or unrecognized outcomes are
  reported as explicit unavailable/error states rather than inferred from HP.
  The T018 native source surface and WSL audit now provide required
  identity-bearing terminal resource components where the game exposes them:
  potion slot identities/order, deck/card identities including curses, relic
  identities and exposed counters, and all three key flags. Partial key-flag
  coverage fails closed as explicit missingness. These identity values are used
  for structured terminal outcomes; sanitized public run context still keeps
  list/dict identity resource values out of normal controller input and reports
  those paths as explicit missing fields.
- Optional PyTorch policy/value plumbing behind the `train` dependency group.
  The T009 model consumes public tactical features, legal action features, and
  the separate `public-context-model-input-v1` encoder introduced by T033;
  scores state-action policy rows; predicts battle survival and terminal
  absolute current HP; and keeps structured terminal resource heads separate.
  Broad training is guarded by a
  fail-closed per-ascension/per-act scale and distribution gate that counts
  stable source identities rather than repeated sampled rows and cannot use A0
  coverage to satisfy A20 requirements. Named `smoke` and `narrow_curriculum`
  overrides may run diagnostic training but never mark broad training ready.
  Checkpoints use `torch-policy-value-checkpoint-v1`, include exact
  trainer-input SHA-256 artifact provenance, controller and information-regime
  summaries, target-source summaries, distribution/source/sampling counts,
  stable source identity summaries, and semantic contract validation on load,
  including public-context schema id, version, feature size, and feature names.
  Raw policy/value diagnostics are reported separately; the merged T029
  model-guided fixed-cohort comparison remains Oracle-like smoke evidence, not
  broad model-strength evidence.
- Versioned A20 battle-start coverage reporting
  (`a20-battle-start-coverage-report-v1`) through
  `--lightspeed-a20-battle-start-coverage`. The report combines a migrated
  portable natural battle-start pool, optional constructed supplement artifact,
  seeded sampled optimization-weight draws, fresh-adapter restore evidence,
  public-context and structured-outcome availability, source identity, and the
  T009 broad-training gate cells. Natural unique-source coverage remains
  separate from repeated sampled rows and constructed supplements; restore
  failures and constructed-source provenance mismatches fail closed while
  ordinary under-coverage remains reportable.
- Versioned Oracle-like teacher dataset reporting
  (`oracle-teacher-dataset-report-v1`) through
  `--oracle-teacher-dataset-report`. The report loads current or migrated
  Oracle teacher JSONL artifacts, optionally links them to a natural
  battle-start source pool and T021 coverage report, records artifact/source
  identities, search statistics, root visit targets, public-context and
  structured-outcome availability, and explicit
  `full_simulator_state_oracle_like` provenance. Unique natural source
  coverage stays separate from repeated teacher rows and root rows. Invalid
  artifacts, missing or mixed information regimes, malformed source identities,
  source-pool mismatches, and T021 source-identity mismatches fail closed;
  ordinary smoke-scale under-coverage is reported rather than treated as a
  command failure.
- Versioned A20 Oracle-like teacher dataset scale-up reporting
  (`oracle-teacher-scaleup-manifest-v1`) through
  `--lightspeed-a20-oracle-teacher-scaleup`. The workflow loads a current or
  migrated A20 natural battle-start source pool, optionally verifies a linked
  T021 coverage report, builds a deterministic source-selection plan from
  rule-defined metadata, collects Oracle-like teacher JSONL artifacts for
  multiple native search budgets on the same selected sources, emits a T022
  report for every budget, and writes a scale-up manifest. It reports selected
  source coverage, generated artifact identities, root rows/visits, native
  simulator steps, teacher-action agreement across budgets, and soft-target
  stability while preserving the `full_simulator_state_oracle_like` evidence
  boundary.
- Versioned Oracle teacher search-guidance bridge reporting
  (`oracle-teacher-search-guidance-bridge-report-v1`) through
  `--oracle-teacher-search-guidance-input`. The workflow loads one selected
  T023 or T043 scale-up budget, verifies the manifest, teacher artifact, T022
  report, and source-pool SHA-256 identities, restores source starts through
  the simulator adapter, rebuilds public tactical/model-input features, and
  emits current trainer-input v6 records with explicit
  `trainer-policy-target-v1` policy targets. Supported policy target kinds are
  `behavior_chosen_action_one_hot`, `oracle_teacher_action_one_hot`, and
  `oracle_soft_visit_distribution`. Teacher action, soft visit target,
  behavior action availability, selected model policy target, structured
  battle outcomes, public-context status, stable source identity, sampling
  component, assisted source-pool kind where applicable, and
  `full_simulator_state_oracle_like` evidence boundary remain separately
  serialized and reported. Optional PyTorch training now consumes
  `record.policy_target`, rejects mixed policy target kinds, and stores policy
  target kind/source counts in checkpoint provenance. This is diagnostic
  search-guidance supervision only, not a controller or model-strength result.
- Versioned search-decision telemetry (`search-decision-telemetry-v1`) and
  aggregate summaries (`search-telemetry-summary-v1`) for current Oracle-like
  native search and fixed restored-battle evaluation. Current Oracle baseline
  decisions now report requested native playout budget, root visits, legal and
  root action counts, native simulator steps, wall-clock time, root value
  spread/gap where available, unsearched/unmapped counts, model calls as zero,
  and explicit unavailable native fields such as tree depth and value
  uncertainty. The telemetry is attached to Oracle controller metadata,
  fixed-evaluation per-battle compute telemetry, Oracle teacher artifacts, and
  formatted fixed-evaluation summaries without changing action selection or
  adding model-guided search.
- Versioned search-guidance checkpoint inference
  (`search-guidance-inference-v1`) for scoring one public `DecisionContext`
  with current `torch-policy-value-checkpoint-v1` checkpoints. The
  framework-neutral result reports per-legal-action logits and eligible-masked
  probabilities, battle survival, terminal absolute current HP, structured
  resource predictions, checkpoint artifact identity, trainer-input
  provenance, target kind/source summaries, information-regime counts, an
  Oracle-like supervision flag, and timing. The optional PyTorch scorer and
  offline CLI smoke path validate current public tactical/context schemas,
  feature sizes, and checkpoint semantic contracts before scoring. This is a
  scorer/inference contract only; it does not run the simulator, choose game
  actions, implement a controller, or provide model-strength evidence.
- Versioned teacher-guidance calibration reporting
  (`teacher-guidance-calibration-report-v1`) for offline comparison between
  T026 checkpoint scores and T024 Oracle teacher policy targets. The report
  loads current trainer-input v6 artifacts and compatible checkpoints, rejects
  mixed target kinds or incompatible checkpoint/trainer provenance, preserves
  trainer/checkpoint artifact identities, separates teacher-target agreement
  from behavior-action agreement, reports cross-entropy/KL/Brier/ranking/top-k
  diagnostics, action-row calibration bins, source coverage, skipped rows, and
  information-regime summaries. This is checkpoint-vs-teacher diagnostic
  evidence only; it does not train, run `sts_lightspeed`, choose actions,
  implement search, benchmark a controller, or make normal-information,
  live-game, broad-training, or controller-strength claims.
- Versioned model-guided Oracle-like search controller
  (`model_guided_oracle_search_v1`) for restored simulator battles. The
  controller runs the current hidden-state native `battle_search` once for the
  requested budget, scores the same public `DecisionContext` through the T026
  checkpoint inference contract, and selects the root action with
  `native_mean_value + weight * model_policy_probability`. Because the native
  search copies hidden simulator state, the controller is explicitly
  `full_simulator_state_oracle_like`. It fails closed on checkpoint,
  action-count, eligibility, action-kind, and available public action-identity
  mismatches; reports native search budget/cost separately from checkpoint
  model calls; preserves checkpoint provenance and model scores in telemetry;
  and records that the T028-era native APIs did not accept model allocation
  hints or leaf values. This is a controller smoke entry point only, not a
  fixed-cohort comparison, normal-information result, live-game validation,
  broad-training result, or controller-strength claim.
- Versioned model-guided search fixed-cohort comparison reporting
  (`model-guided-search-fixed-comparison-v1`) for the M1 Oracle-like sandbox.
  The command loads one immutable fixed cohort, evaluates baseline
  `OracleSearchController` and T028 `ModelGuidedOracleSearchController` on the
  same restored starts, fails closed on source/order mismatches or sub-report
  failures, and writes a JSONL report with per-battle comparison rows,
  separate natural-weighted, encounter-macro, room-type-macro, and per-stratum
  outcome aggregates, configured native-playout budget checks, observed
  wall-clock/native-step/model-call telemetry, checkpoint provenance, and an
  explicit `full_simulator_state_oracle_like` diagnostic evidence boundary.
  This is fixed-cohort comparison plumbing and smoke evidence only, not
  normal-information, live-game, broad-training, performance-improvement, or
  controller-promotion evidence.
- Versioned model-guided Oracle-like search v2 comparison
  (`model-guided-search-fixed-comparison-v2`) for refreshed diagnostic
  checkpoint provenance. The v2 controller remains
  `full_simulator_state_oracle_like`, uses root-selection-only guidance with
  score `native_mean_value + weight * model_policy_probability * multiplier`,
  where `multiplier = sqrt(total_root_visits / native_visits)`, compares
  baseline Oracle search, T028 v1, and T035 v2 on identical restored starts,
  and reports separate telemetry for native playouts, model calls, native
  simulator steps, root mapping, truncation, and restore failures. The
  T035-era native APIs did not accept model allocation hints or leaf values.
  This is diagnostic comparison evidence only, not normal-information,
  live-game, broad-training, performance-improvement, or
  controller-promotion evidence.
- Potion-enabled Oracle-like search root mapping repair and comparison
  reporting. Native search results with positive
  `unmapped_search_edge_count` may now preserve mapped legal root rows as
  valid telemetry instead of failing only because total native root visits
  exceed mapped root-row visits. Overcounted rows and unexplained visit
  mismatches still fail closed. The `oracle-potion-fixed-comparison-v1` report
  compares no-potion and potion-enabled Oracle search on identical restored
  starts with equal native playout budgets, action-space provenance, root
  mapping failure counts, unmapped edge telemetry, potion inventory deltas,
  terminal HP, native simulator steps, model calls, and the explicit
  `full_simulator_state_oracle_like` engineering-evidence boundary.
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests And Runtime Evidence

- `810` tests pass on Windows Python as of the T070 implementation review. In an
  uninstalled checkout, set `PYTHONPATH=src` (or install the package) before
  invoking the CLI directly.
- The two CommunicationMod fixture smokes pass.
- `python -m compileall -q src tests` passes.
- `ruff check src tests` and `ruff format --check src tests` pass.
- The T010 A20 natural calibration over seeds `1..100` reports 2,303
  non-combat decisions with complete provenance and no driver problems;
  unreached Boss relic screens remain explicit natural-coverage gaps.
- The legacy ordered `sts_lightspeed` patch-stack build passed from external
  commit `7476a81` before T017 retired that workflow. A T004 A20 pool over
  seeds `1..3` contains 13 natural starts with 10 reported wins, 3 losses, no
  missing completed outcome, and 13/13 fresh-adapter portable restores.
- T005's legacy clean WSL patch-stack gate freezes 8 unique starts from that
  pool and evaluates them through fresh portable restores with the
  normal-public `preferred_kind` controller. The plumbing run reports 5 wins
  and 3 losses, no truncation or evaluation errors, and all three aggregate
  views. This is fixed-evaluation evidence only, not an A20 policy-strength
  result.
- The T011 clean WSL gate and A20 tactical-feature audit pass. Across
  one bounded seed it observed 81 battle snapshots and 497 legal actions with
  `public-tactical-v2` state/action compatibility sizes of 4,634/92 and no
  required simulator-projection failures. A captured CommunicationMod audit
  covers 3,347 battle snapshots; its documented live-missing fields remain a
  deployment constraint for T013, not an implicit simulator fallback.
- T013 validates the live adapter against captured CommunicationMod messages:
  public-state sanitization, duplicate actions, target/potion command mapping,
  explicit targetability fallback, complete runtime provenance, and no-command
  failure paths. Across the capture corpus, all 2,352 states with a playable
  targeted card and a positive-HP non-gone monster produce target actions.
- T014 validates the raw native public-projection capability over seeds `1..3`
  at A20 with 289 current decision screens: `BATTLE=236`, `CARD_SELECT=2`,
  `EVENT_SCREEN=4`, `MAP_SCREEN=16`, and `REWARDS=31`. The canonical
  `build-py` audit reports 1,209 resource snapshot comparisons, 0 resource
  mismatches, 289 candidate-action parity passes, 289 checkpoint projection
  passes, no checkpoint failures, and explicit coverage gaps for
  `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and `TREASURE_ROOM`.
- T016 validates public-context artifact propagation and replay audit over a
  WSL A20 bounded run with 327 current decision screens, 15 battle-start
  records, 15/15 replay public-context matches, and 0 parity, schema,
  forbidden-field, replay, or run failures. The current natural coverage gaps
  remain `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and `TREASURE_ROOM`.
  The same post-review WSL smoke and battle-training-readiness gates pass.
- The T017/T018/T008-managed pinned external source integration currently
  validates from manifest `sts-lightspeed-source-manifest-v1` version 1. The
  canonical source verifier builds integration commit
  `fee272f1ae21c283ad2161f55293cfe6d714134a`,
  initializes `json` and `pybind11`, imports `slaythespire.StepSimulator`, and
  asserts the current native capability inventory including
  `native_battle_search_root`, `native_root_prior_allocation`,
  `native_battle_search_v2_tree_internal`,
  `native_battle_search_v2_tree_geometry`,
  `native_terminal_resource_identity`, and
  `constructed_battle_start_transforms`. The verifier also exercises the
  Search v2 tree-internal policy-prior and learned-leaf-value boundary with
  explicit native provenance. Missing-manifest and wrong-commit verifier
  checks fail nonzero. The T062 review validated this exact source/runtime
  pairing through the verifier, focused native tests, and a failed-shard smoke.
  The required WSL smoke, public-projection capability, public-context replay,
  and battle-training-readiness gates remain part of the pinned-source gate.
- T006 validates Oracle-like search teacher collection and fixed-cohort
  comparison on the T004/T005 A20 smoke data. A fresh pool over seeds `1..3`
  produced 13 natural starts; the frozen cohort selected 8 starts with
  identity `c29d7852c941d592`. Teacher collection at 20 native simulations
  produced 13 rows, 120 root rows, 260 root visits, and 3,621 native simulator
  steps with deterministic non-timing JSONL content across repeated runs.
  Oracle fixed evaluation at 20 simulations evaluated both `highest_mean` and
  `most_visits` on the same cohort with no truncations, restore errors, or
  root-mapping failures.
- T012/T018 validate structured battle resource outcome plumbing and native
  identity coverage. The WSL resource-outcome audit over seeds `1..3` at A20
  reports 13 natural starts, 13 completed battles, 10 `PLAYER_VICTORY`, 3
  `PLAYER_LOSS`, 13 available structured outcome records, no completed battles
  missing outcomes, no pool or structural audit problems, no unsupported native
  fields, and no T018 identity gate problems. The post-review WSL smoke and
  battle-training-readiness gates pass.
- T008 validates conservative constructed A20 battle-start supplements over a
  portable natural pool. The accepted WSL audit over seeds `1..3` at A20
  reported 13 natural source starts, 3 first-battle sources, 10 later-battle
  sources, 39 transform audit rows, 11 constructed rows, resulting
  distributions `natural_run: 13` and `constructed_supplement: 11`, no
  unsupported native operations, no cap/Boss/ascension violations, and source
  public-context status available for every audit row. Repeating the same
  audit over the same pool, policy seed, and pinned native source produced
  matching artifact SHA256 digests and identical record manifests. The
  post-review WSL source verifier, smoke, and battle-training-readiness gates
  pass with `constructed_battle_start_transforms` in the source identity.
- T009 validates optional PyTorch search-guidance plumbing. The accepted local
  review ran focused T009 tests, full Windows tests, compileall, ruff, both
  CommunicationMod fixture smokes, trainer-input preflight, and a one-epoch
  smoke-override PyTorch training command that wrote a checkpoint while still
  reporting `broad training allowed: no` and
  `search-guided fixed evaluation: not_run`. Regression checks confirm that
  repeated samples from the same source checkpoint do not increase unique
  coverage, missing stable source identity fails closed, checkpoint
  provenance contains the trainer-input SHA-256 artifact id and controller /
  information-regime summaries, and tampered semantic checkpoint fields or
  incomplete training-data provenance are rejected on load. The accepted WSL
  smoke, battle-training-readiness, battle-start pool, and fixed-evaluation
  gates pass; the fixed-evaluation smoke selected 8 battles from 13 natural
  starts and reported 5 wins, 3 losses, 0 truncations/errors, and evaluation
  successful.
- A post-backlog repository review on 2026-06-24 found the current `main`
  quality gates clean: 475 Windows tests, compileall, ruff check,
  ruff format check, both CommunicationMod fixture smokes, default CLI import
  without importing PyTorch, WSL `--lightspeed-smoke`, and WSL
  `--lightspeed-battle-training-readiness` all pass on the pinned T008
  `sts_lightspeed` source.
- After T019 merged on 2026-06-24, the behavior-preserving refactor gate
  passed on `main`: 479 Windows tests, compileall, ruff check, ruff format
  check, both CommunicationMod fixture smokes, default CLI import without
  importing PyTorch, and diff whitespace check. `ruff format --check` emitted
  non-fatal cache-write warnings but exited successfully.
- T021 validates the A20 battle-start coverage report. The accepted local gate
  passed 489 Windows tests, compileall, ruff check, ruff format check, both
  CommunicationMod fixture smokes, and focused coverage/CLI tests. The WSL
  smoke-scale coverage chain over seeds `1..3` at A20 reported 13 natural
  starts from 3 source runs, 13 unique natural sources, 13 completed battles,
  13 available structured outcomes, 13/13 fresh-adapter restores, 16 sampled
  optimization-weight draws, and 11 accepted constructed rows from 39 audit
  rows. The combined gate input had 40 training rows
  (`natural_run=20`, `stratified_training=9`,
  `constructed_supplement=11`) and 13 unique natural sources. The T009 broad
  training gate correctly remained closed: A20 Act 1 was below the record and
  unique-source thresholds and constructed rows lacked constructed-context and
  terminal-outcome labels; A20 Acts 2--4 had zero rows.
- T022 validates the Oracle-like teacher dataset report. The accepted local
  gate passed 498 Windows tests, compileall, ruff check, ruff format check,
  both CommunicationMod fixture smokes, focused teacher-report, teacher
  artifact, source-pool linkage, T021 coverage linkage, schema-failure, and
  CLI tests. The accepted WSL smoke-scale report chain at A20 produced 41
  natural starts, 41 teacher rows, 41 unique natural teacher sources, 400 root
  rows, 820 root visits/search simulations, and 11,985 native simulator steps.
  The report loaded schema `oracle-teacher-dataset-report-v1` version 1,
  matched the supplied source pool and T021 natural-pool identity, reported no
  metadata mismatches, and kept the evidence boundary explicit:
  `full_simulator_state_oracle_like`, not normal-information, live-game, broad
  training, or controller-strength evidence. The T021-linked broad-training
  gate correctly remained closed because the smoke-scale data was Act 1 only
  and below the required per-act thresholds.
- T023 validates the A20 Oracle-like teacher scale-up workflow. The accepted
  local gate passed 508 Windows tests, compileall, ruff check, ruff format
  check, both CommunicationMod fixture smokes, focused scale-up and CLI tests,
  and diff whitespace checks. The WSL source verifier rebuilt and validated
  the pinned `sts_lightspeed` integration commit
  `242344c57c17c784708a6f072c905febc3f96527`. The accepted WSL smoke-scale
  chain at A20 produced 41 natural starts from 10 source runs, 41 available
  structured outcomes, 41/41 restore and public-context matches, 73 T009 gate
  training rows, and 41 unique natural sources; the broad-training gate
  remained closed because Act 1 stayed below the record threshold and Acts 2--4
  had zero records. The T023 scale-up selected 32 of 41 sources with seed 1,
  all A20 Act 1 (`MONSTER=31`, `ELITE=1`), and generated teacher artifacts and
  T022 reports at budgets 20, 50, and 100. Each budget produced 32 teacher
  rows and 331 root rows; root visits/search simulations were 640, 1,600, and
  3,200; native simulator steps were 9,321, 23,432, and 46,948. Cross-budget
  teacher-action agreement was 12/32 sources for all budgets and 52/96 pairwise
  comparisons; soft targets were available for all 32 selected sources with
  mean pairwise total-variation distance 0.042917 and maximum 0.120000. The
  evidence boundary remained explicit: `full_simulator_state_oracle_like`, not
  normal-information, live-game, broad-training, or controller-strength
  evidence.
- T024 validates the Oracle teacher search-guidance bridge. The accepted local
  gate passed 517 Windows tests, compileall, ruff check, ruff format check,
  both CommunicationMod fixture smokes, focused bridge/schema/trainer/PyTorch
  and CLI tests, and diff whitespace checks. The maintainer review reran the
  WSL source verifier against pinned integration commit
  `242344c57c17c784708a6f072c905febc3f96527`, then reran the T024 bridge over
  the accepted T023 smoke artifacts at budget 100. The WSL bridge consumed 32
  teacher rows, emitted 32 trainer-input v6 rows, skipped none, restored all
  rows with `seed_action_trace`, reported 32 available public contexts and 32
  available structured outcomes, and wrote trainer artifact SHA-256
  `cca1960ecf1684470245f9bafc2afde3a0d5a77f5901981fef556d1ebf15797c`.
  Preflight over the generated trainer artifact passed model-input packing,
  context rebuild, and scoring-shape checks with 32 records, 4,634 snapshot
  features, 92 action features, and 331 action rows. The T009 broad-training
  gate remained closed as expected for smoke-scale Act 1 data. Windows PyTorch
  also wrote and loaded a one-epoch diagnostic checkpoint under the named
  `smoke` override, preserving `oracle_teacher_action_one_hot` and
  `oracle_teacher_row.teacher_action` provenance; this remains diagnostic
  Oracle-like supervision, not normal-information or controller-strength
  evidence.
- T025 validates the search telemetry baseline. The accepted local gate passed
  521 Windows tests, compileall, ruff check, ruff format check, both
  CommunicationMod fixture smokes, focused telemetry/Oracle/fixed-evaluation
  and CLI tests, and diff whitespace checks. The maintainer review reran the
  WSL source verifier against pinned integration commit
  `242344c57c17c784708a6f072c905febc3f96527`, then ran a smoke WSL chain that
  generated 4 A20 Act 1 natural battle starts, selected a 4-battle fixed
  cohort, and evaluated Oracle search at 5 native simulations. The
  highest-mean telemetry summary reported `search-decision-telemetry-v1`,
  67 decisions, 335 requested simulations/root visits, 3,307 native simulator
  steps, model calls total 0, 0 root mapping failures, and explicit unavailable
  `tree_depth` and `value_uncertainty`. The most-visits diagnostic reported
  the same schema with 60 decisions, 300 requested simulations/root visits,
  2,984 native simulator steps, model calls total 0, and 0 root mapping
  failures. The run is telemetry plumbing evidence only, not controller
  promotion or A20 strength evidence.
- T026 validates the checkpoint inference/scoring contract. The accepted local
  gate passed 527 Windows tests, compileall, ruff check, ruff format check,
  both CommunicationMod fixture smokes, focused inference/checkpoint/CLI tests
  with a smoke checkpoint, and diff whitespace checks. The maintainer review
  confirmed the WSL Python environment still lacks PyTorch
  (`ModuleNotFoundError: No module named 'torch'`). WSL simulator gates are not
  required for T026 because it is an offline checkpoint scorer contract and
  does not run `sts_lightspeed`, advance a simulator, choose actions, or claim
  controller strength.
- T027 validates the offline teacher-guidance calibration report. The accepted
  local gate passed 535 Windows tests, compileall, ruff check, ruff format
  check, both CommunicationMod fixture smokes, focused calibration/CLI tests,
  and diff whitespace checks. The maintainer review found no compatible
  external T024 `.pt` smoke checkpoint under the checked local/WSL artifact
  locations, so no optional artifact-level smoke metrics were added. This
  remains checkpoint-vs-Oracle-teacher diagnostic evidence only, not
  normal-information, live-game, broad-training, search-controller, or
  controller-strength evidence.
- T028 validates the first model-guided Oracle-like search controller. The
  accepted local gate passed 543 Windows tests, compileall, ruff check, ruff
  format check, both CommunicationMod fixture smokes, focused controller,
  fixed-evaluation, CLI, export, Oracle-search, and telemetry tests, and diff
  whitespace checks. Regression coverage confirms native
  `oracle_search_model_calls` stays separate from checkpoint inference calls,
  guidance rows fail closed on action-kind and available public-action-identity
  mismatches, and fixed-evaluation telemetry handles optional scalar `None`
  values without losing versioned search telemetry. The accepted WSL evidence
  included the canonical pinned-source verifier, standard simulator smoke, and
  battle-training-readiness gates. A WSL model-guided fixed-evaluation smoke
  using ignored artifacts under `artifacts/t028-wsl-smoke/` exercised 8 A20
  restored battles, 123 model-guided Oracle decisions, 123 checkpoint model
  calls, 3 requested native playouts per decision, 0 root mapping failures,
  0 truncations, and 0 errors. A maintainer audit also rebuilt a Python 3.13
  shim directly from pinned integration commit
  `242344c57c17c784708a6f072c905febc3f96527`, regenerated a small A20
  pool/cohort, and reran the T028 controller path successfully over 4 restored
  battles with 61 decisions and 61 model calls. This remains
  `full_simulator_state_oracle_like` smoke evidence only, not
  normal-information, live-game, broad-training, fixed-comparison, or
  controller-strength evidence.
- Documentation lifecycle hygiene now has a local regression guard:
  `tests/test_task_docs.py` fails if individual task documents reintroduce
  mutable `Status:` lines, or if current contract docs recreate a line-level
  `Status:` field outside the canonical task index.
- T029 validates the first fixed-cohort model-guided search comparison report.
  The accepted local gate passed 548 Windows tests, compileall, ruff check,
  ruff format check, both CommunicationMod fixture smokes, focused comparison
  and CLI tests, and diff whitespace checks. The accepted WSL evidence
  included the canonical pinned-source verifier, standard simulator smoke, and
  battle-training-readiness gates. The WSL T029 comparison smoke used an
  explicitly reported ignored A20 cohort/checkpoint/shim artifact set under
  `artifacts/t029-wsl-smoke/`, matched source starts across controllers,
  evaluated 8 restored battles, and reported baseline Oracle search and
  model-guided Oracle-like search both at 5 wins and 3 losses. The configured
  native playout budget was equal at 5 per decision; observed native simulator
  steps were 5,178 for each controller; model calls were 0 for baseline and
  120 for model-guided; restore failures, truncations, and errors were all 0.
  This is `full_simulator_state_oracle_like` smoke-scale comparison evidence
  only, not normal-information, live-game, broad-training, fixed-cohort
  improvement, or controller-promotion evidence.
- T030 validates the documentation-only M1 synthesis and post-M1 task-batch
  publication. The accepted maintainer review found no actionable findings and
  passed `pytest tests/test_task_docs.py -q`, diff whitespace checks, a local
  Markdown reference scan, a task-index lifecycle/link scan with 35 rows and
  only T030 `READY` at review time, and the stale `Status:` scan. No code,
  artifact, or WSL simulator gate was required. The synthesis records that M1
  succeeded as Oracle-like search plumbing but did not show controller
  improvement, and it keeps follow-up implementation gated behind explicit
  task states.
- T031 validates the first post-M1 A20 coverage refresh and distribution-gap
  diagnosis. The accepted PR updated `docs/experiment_log.md` only and kept
  generated artifacts under ignored `artifacts/t031-a20-coverage-refresh/`.
  The WSL chain used pinned `sts_lightspeed` integration commit
  `242344c57c17c784708a6f072c905febc3f96527`, 50 A20 source episodes, and a
  500-step cap. It produced 218 natural battle starts from 50 terminal source
  runs, 173 accepted constructed rows from 654 audit rows, 256 sampled
  optimization-weight draws, 218/218 successful restore/public-context
  comparisons in the reported coverage artifact, and no artifact command
  problems. All natural starts were Act 1; no Act 1 Boss or later-act battle
  starts were reached. The T009 gate remained closed: A20 Act 1 failed because
  constructed rows lacked current public-context and structured-outcome labels,
  while A20 Acts 2--4 had zero records and zero unique sources. Maintainer
  review reran the pinned-source verifier, verified artifact SHA-256 values,
  parsed the coverage report, and ran a lightweight WSL coverage read/restore
  smoke on the reported artifacts. This is healthy artifact and distribution
  evidence, not broad training, teacher-refresh, fixed-comparison,
  controller-strength, live-game, or normal-information evidence.
- T032 validates the narrow teacher/checkpoint diagnostic refresh over the T039
  source contract. The accepted PR added an explicit `t032_t039_narrow`
  source-selection mode for T023 scale-up and kept generated artifacts under
  ignored paths. The regenerated source pool used 40 shards x 25 terminal runs
  over seeds `1..1000` with 8 WSL workers, A20, 500 steps,
  `oracle_search_v1_highest_mean_s20`, no battle potions, and the separate
  `stochastic-v1` non-combat driver. Coverage restoration was rerun as 40
  shard-level jobs with 8 workers. The pool had 4,688 natural starts,
  31 Act 1 Boss starts, 3 Act 2 starts, 4,688/4,688 restore/public-context
  matches, and 4,688 available structured outcomes. T032 selected all 31
  Act 1 Boss starts, all 3 Act 2 starts, and 64 deterministic Act 1 non-Boss
  background starts with seed `32039`. Teacher budgets 20, 50, and 100 used the
  same 98 source identities, each producing 98 teacher rows. The budget-100
  bridge emitted 98 trainer-input v6 rows with `oracle_teacher_action_one_hot`
  targets, a one-epoch Windows PyTorch checkpoint was trained under the named
  `narrow_curriculum` override, and calibration evaluated 98/98 rows with
  top-1 20/98, top-3 65/98, mean CE/KL 1.786224, and ECE 0.014812. The T009
  broad-training gate remained closed because Act 2 had only three selected
  rows and Acts 3--4 had zero rows. Maintainer review verified artifact hashes,
  reran the pinned-source verifier, passed 565 Windows tests, compileall,
  ruff, format check, both CommunicationMod fixture smokes, task-doc checks,
  and diff whitespace checks. This is diagnostic Oracle-like supervision
  evidence only, not normal-information, live-game, broad-training,
  controller-strength, or promotion evidence.
- T035 adds the v2 model-guided Oracle-like search controller and fixed-cohort
  comparison report. Maintainer review passed 569 Windows tests, compileall,
  ruff, format check, both CommunicationMod fixture smokes, task-doc checks,
  diff whitespace checks, the WSL pinned-source verifier, and WSL smoke and
  readiness gates. The accepted smoke artifact used 13 natural A20 Act 1 starts
  from three source runs, fixed cohort id `3957b3c5c346bbc7`, and a two-row
  diagnostic checkpoint `t035-smoke.pt` with sha256
  `4d9c2ff8776e87fc6884821c9745c3033084739c4f6b22f1d550280c2f11864a`.
  The comparison schema was `model-guided-search-fixed-comparison-v2`; baseline,
  T028 v1, and T035 v2 all finished 5W/3L across eight restored battles, made
  116 decisions each, used equal three-playout native search budgets, recorded
  model calls as 0/116/116, and reported no restore failures, truncations,
  controller errors, or root-mapping failures. This is diagnostic smoke
  evidence only and does not promote the controller.
- T040 adds `expert_non_combat_v1`, a seeded, stochastic, public-input A20
  heuristic non-combat driver for source generation, and the offline
  `expert-non-combat-source-coverage-comparison-v1` report. Maintainer review
  verified the ignored `artifacts/t040-scale/` hashes and shard statuses,
  passed 582 Windows tests, compileall, ruff, format check, both
  CommunicationMod fixture smokes, focused T040 tests, task-doc checks, diff
  whitespace checks, and the WSL pinned-source verifier. The accepted
  three-arm A20 source comparison used 1,000 terminal source runs per arm:
  `stochastic_s20` produced 4,688 starts, 31 Act 1 Boss starts, and 3
  later-act starts; `expert_s20` produced 4,848 starts, 49 Act 1 Boss starts,
  and 7 later-act starts; `expert_s100` produced 5,519 starts, 113 Act 1 Boss
  starts, and 28 later-act starts. The T040 scale and reachability gates passed,
  but the T009 broad-training gate remained closed for all arms. This is
  source-distribution evidence only, not controller promotion evidence. The
  raw GB-scale T040 pools are not a required downstream input; durable evidence
  is the merged command/report surface, PR-reported hashes, and this status
  summary. Future assisted or teacher scale artifacts that are expected to feed
  later tasks must use an explicit ignored/local retention manifest instead of
  relying on review-worktree leftovers.
- T041 repairs potion-enabled Oracle-like root mapping and adds the
  `oracle-potion-fixed-comparison-v1` fixed-cohort comparison. Maintainer
  review verified artifact hashes, passed 573 Windows tests, compileall, ruff,
  format check, both CommunicationMod fixture smokes, focused Oracle/potion
  comparison tests, task-doc checks, diff whitespace checks, the WSL
  pinned-source verifier, and a WSL no-potion vs potion-enabled restored
  fixed-cohort comparison. The accepted smoke artifact used one Hexaghost Act 1
  Boss start from seed `122`, cohort id `67bd71731b750f87`, and comparison
  artifact sha256
  `8224d43885f1cbccbdf65debe195ef581f0bbe2141b53e4a1feb7a4b33ba5fc5`.
  Both arms used 20 native playouts per decision, reported zero root mapping
  failures and zero unmapped search edges on the smoke cohort, finished 0W/1L,
  and preserved restore, public-context replay, and structured outcomes. The
  potion-enabled arm recorded one potion slot item added and one removed. This
  is engineering smoke evidence only, not performance-improvement or promotion
  evidence.
- T042 adds the `assisted_run` complete-run source-generation distribution,
  versioned assistance schedules, assisted source-pool schema, assisted replay
  restore verification, and WSL-facing source/coverage/report commands. The
  accepted schedules are `assist_0`, `assist_hp25`, `assist_hp50`,
  `assist_hp50_potion_elite_boss`, and `assist_hp75_potion`. Assistance uses
  the simulator-owned `rebuild_battle_start` surface before battle decisions
  and records requested/actual resource changes, source identity, schedule
  version, policy seed, information regime, distribution tag, and screen/battle
  provenance. Natural pool loading remains strict, and assistance provenance is
  kept out of normal controller/model inputs. The accepted scale evidence used
  1,000 A20 terminal source runs per arm, 16 source/coverage workers, and
  stable ignored artifacts under
  `artifacts/t042-assisted-source-scale-pr39/runs1000_s20_workers16/`.
  `assist_0` reached 0 later-act starts, while assisted arms reached 26, 34,
  and 183 later-act starts for `assist_hp50`,
  `assist_hp50_potion_elite_boss`, and `assist_hp75_potion` respectively; all
  arms had 0 truncated runs and successful restore evidence. The T009
  broad-training gate remains closed, and this is assisted source-distribution
  evidence only, not natural A20, normal-information, live-game, broad-training,
  controller-strength, or final-agent performance evidence. The T042 PR also
  established the bounded-memory GB-scale finalization pattern now recorded in
  `docs/project_architecture.md` and `docs/tasks/README.md`: stream JSONL
  source merges and aggregate coverage/comparison reports from shard summaries
  and artifact identities instead of loading every shard record into memory.
- T033 adds `public-context-model-input-v1`, a separate 103-feature public
  context encoder for sanitized `public_run_context` plus
  `public_context_status`. `ModelInputBatch` now carries explicit public
  context feature schema id/version/size/names, feature rows, and missingness
  summaries. PyTorch training, reports, checkpoint save/load, and scorer
  validation thread that schema separately from public tactical features.
  Hidden-field firewall and T042 assistance non-leakage tests fail closed, and
  legacy or unavailable context remains explicit missingness rather than
  ordinary zero context. Maintainer review passed 594 Windows tests,
  compileall, ruff, format check, both CommunicationMod fixture smokes,
  focused model-input/PyTorch/preflight tests, task-doc checks, and diff
  whitespace checks.
- T043 adds the assisted Oracle teacher scale-up path
  (`--lightspeed-a20-assisted-oracle-teacher-scaleup`) and extends the teacher
  bridge/calibration reports for assisted source pools. Assisted scale-up emits
  `input_artifacts.assisted_pool`, uses the
  `seeded_uniform_assisted_run_source_sample` selection contract, preserves
  assistance level, distribution kind, act, room type, encounter, and source
  identity summaries through trainer generation metadata and calibration
  reports, and keeps `assisted_run` sampling separate from natural sampling.
  Assisted bridge artifacts are stamped as T043 while the older natural bridge
  path remains T024-compatible. The accepted smoke evidence is wiring-scale
  and `full_simulator_state_oracle_like`; it is not broad A20 training,
  natural A20 performance, normal-information performance, controller
  promotion, or live-game validation. Maintainer review passed 601 Windows
  tests, compileall, ruff, format check, both CommunicationMod fixture smokes,
  focused teacher scale-up/search-guidance/calibration tests, task-doc checks,
  and diff whitespace checks.
- T044 adds the `de-assisted-fixed-cohort-comparison-v1` report and
  `--lightspeed-de-assisted-fixed-cohort-comparison` workflow. It compares
  identical restored starts across baseline Oracle-like search,
  `model_guided_oracle_search_v2` using regenerated T043 checkpoint
  provenance, a raw public checkpoint-policy diagnostic controller, and a
  scripted public baseline. Fixed cohorts now preserve T042
  `assistance_history`; `assisted_run` cohorts fail closed when that
  provenance is missing, and assisted fixed starts restore by replaying the
  T042 transforms. Maintainer review verified the retained T042 runs1000 input
  hashes, regenerated T043 manifest/teacher/trainer/bridge/checkpoint hashes,
  fixed cohort hashes, and both T044 comparison hashes. The accepted smoke
  evidence used cohort `a336ffb1fda9ed7e` for `assist_0` and
  `e99a0938307c0e7a` for `assist_hp50`; both reports had matched sources,
  equal one-playout search-arm budgets, no restore/truncation/controller
  errors, and no model-guided outcome improvement over baseline. The
  `assist_hp50` comparison was sharded into 16 WSL workers, all shard reports
  passed, and the merged comparison recorded 23W/15L for both baseline and
  model-guided search, 11W/27L for raw checkpoint policy, and 19W/19L for the
  scripted baseline. Maintainer review passed 611 Windows tests, compileall,
  ruff, format check, both CommunicationMod fixture smokes, focused T044
  comparison/search-guidance/fixed-evaluation tests, task-doc checks, and diff
  whitespace checks. This is diagnostic smoke-scale evidence only, not
  controller promotion, broad-training evidence, normal-information
  performance, natural A20 performance, live-game validation, or final-agent
  evidence.
- T045 adds the offline `post-t044-failure-analysis-report-v1` report and
  `--post-t044-failure-analysis-report` workflow. It consumes explicit T044
  `de-assisted-fixed-cohort-comparison-v1` artifacts plus linked T043 artifact
  identities, preserves source/cohort/checkpoint provenance, rejects schema,
  source, required-arm, provenance, and information-regime mismatches, and
  reports unavailable diagnostics rather than inferring missing fields. The
  accepted smoke analysis used the retained T044 `assist_0` and `assist_hp50`
  comparison artifacts, found 35 unique source starts and 446 decision rows,
  recorded model-guided search overrides at 0/446, kept model-guided outcomes
  tied with baseline on all 35 battles, found raw checkpoint policy worse than
  the scripted baseline on 9/35 battles, and reported model top action in the
  native top 1/top 3 on 160/446 decisions. The failure taxonomy marked
  `integration-too-late`, `distribution-mismatch`, and `model-too-weak` as
  active signals, left `teacher-label-noisy` unavailable because no linked
  calibration report was supplied, and found no action-space/fallback issue in
  the smoke inputs. The recommended next paths are native root-prior
  allocation, root-prior guided comparison, assisted training repair, and
  de-assisted distribution repair. This is offline diagnostic evidence only,
  not new training, native API work, controller promotion, broad-training
  evidence, normal-information performance, natural A20 performance, or
  live-game validation.
- T046 adds the native `StepSimulator.battle_search_with_root_priors` surface,
  STSRL adapter validation for occurrence-safe root-prior stable ids, and the
  `native-root-prior-allocation-report-v1` smoke workflow. The source manifest
  now pins `lsmfttb/sts_lightspeed` `refs/heads/stsrl/main` at
  `9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a` with native capability
  `native_root_prior_allocation`. The verifier materializes cached submodules
  from exact commit objects, builds a clean disposable pinned-source worktree,
  and asserts the root-prior API plus allocation metadata/root-row fields.
  Maintainer review passed 623 Windows tests, compileall, ruff, format check,
  both CommunicationMod fixture smokes, focused T046/task/CLI tests, diff
  whitespace checks, the WSL pinned source verifier, and a WSL root-prior
  allocation smoke. The accepted smoke used seed `1`, A20, a 20-playout
  budget on a Cultist battle, and reported baseline visits `20`, uniform
  allocation `[4, 4, 4, 4, 4]`, one-hot allocation `[16, 1, 1, 1, 1]`, zero
  root mapping failures, and the
  `full_simulator_state_oracle_like` information regime. This is native
  search-surface smoke evidence only, not a root-prior fixed-cohort
  comparison, controller promotion, broad-training evidence,
  normal-information performance, natural A20 performance, live-game
  validation, or final-agent evidence.
- T047 adds `RootPriorGuidedSearchController`, the
  `root-prior-guided-search-comparison-v1` report, and
  `--lightspeed-root-prior-guided-search-comparison`. The controller scores the
  public decision context with a T043-compatible checkpoint, maps checkpoint
  policy probabilities through occurrence-safe stable action identities into
  the T046 native root-prior allocation surface, and selects final actions only
  from native root statistics. Maintainer review passed 629 Windows tests,
  compileall, ruff, format check, both CommunicationMod fixture smokes,
  focused T047/CLI/task tests, diff whitespace checks, the WSL pinned source
  verifier, and a same-runtime WSL probe showing Python 3.14.4 can import both
  torch `2.9.1+debian` and the active CPython 3.14 `slaythespire` build with
  `battle_search_with_root_priors`. The accepted smoke comparison used fixed
  cohort `875ea52e3df4cb93`, checkpoint sha256
  `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`, and
  comparison artifact sha256
  `fb237dd2067d3f715613ded74db97231a216db204f78e59d265cb47e22ef6a43`.
  On record range `0:1`, all required arms used 20 native root playouts,
  restored the same Blue Slaver A20 Act-1 start, had no restore,
  truncation, controller, allocation metadata, or root-mapping failures, and
  reported baseline Oracle search `0W/1L`, post-search
  `model_guided_oracle_search_v2` `0W/1L`, and root-prior guided search
  `1W/0L`. This is one-record smoke-scale, full-simulator-state Oracle-like
  evidence only, not controller promotion, broad-training evidence,
  normal-information performance, natural A20 performance, live-game
  validation, or final-agent evidence.
- T048 scales the T047 root-prior guided comparison and adds
  `--root-prior-guided-search-comparison-task-id` so scale-up artifacts can
  record `comparison_config.task_id` as `T048` while preserving the T047 schema.
  Maintainer review verified retained artifact hashes, parsed both retained
  `root-prior-guided-search-comparison-v1` reports with the current loader,
  passed 629 Windows tests, compileall, ruff, format check, both
  CommunicationMod fixture smokes, focused root-prior/CLI tests, task-doc
  checks, diff whitespace checks, the WSL pinned source verifier, and a
  same-runtime WSL probe using
  `/home/lsmft/stsrl-spikes/py313-torch/bin/python` with
  `/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch`. The current
  T046-compatible cohort `875ea52e3df4cb93` used 8 workers over record range
  `0:8`, report sha256
  `d9d441f75d21a43aea8884f234f06de819060a2f6f1c421ba84ab23a719efb98`, and
  produced baseline Oracle search `5W/3L`, post-search
  `model_guided_oracle_search_v2` `5W/3L`, and root-prior guided search
  `6W/2L`. The assisted `assist_0` runs1000 cohort `a336ffb1fda9ed7e` used
  16 workers over record range `0:21`, report sha256
  `5807c4255c97a5018e189198180435e077b4d2698b66f6227e9580cb845cb398`, and
  produced baseline `11W/10L`, post-search `11W/10L`, and root-prior
  `13W/8L`. Both reports had matched sources, equal configured 20-playout
  native budgets across required search arms, no restore/truncation/controller
  errors, no root-mapping failures, and no malformed allocation metadata. This
  is fixed-cohort, full-simulator-state Oracle-like evidence only; it is not
  controller promotion, broad-training evidence, complete-run reachability
  evidence, normal-information performance, natural A20 performance,
  live-game validation, or final-agent evidence.
- T049 extends the T036/T037 complete-run source collection path with
  `--search-battle-controller` choices for baseline `oracle_search_v1`,
  checkpoint-guided `model_guided_oracle_search_v2`, and
  `root_prior_guided_oracle_search_v1`, while keeping the separately named
  stochastic non-combat driver and routed provenance. Maintainer review passed
  634 Windows tests, compileall, ruff, format check, task-doc checks, diff
  whitespace checks, both CommunicationMod fixture smokes, the WSL pinned
  source verifier, and same-runtime WSL probes using
  `/home/lsmft/stsrl-spikes/py313-torch/bin/python` with
  `/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch`. The accepted
  bounded smoke used matched seeds `1..2`, A20, step cap 500,
  `initial_no_potions`, `stochastic-v1`, native root budget 20, checkpoint
  sha256 `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`,
  source manifest sha256
  `956234d3221738654ab35a8f1279f9411c62ba86447a65b4aca64dcf00bf287b`, and
  reachability report sha256
  `bac0a5cc8b0c719c9d902f8147793529ae12b79d0011d025276ae572504095e2`.
  Baseline and post-search model-guided arms produced 10 Act-1 starts and
  8W/2L; root-prior produced 11 Act-1 starts and 9W/2L. Boss and later-act
  reachability were zero in all arms. This is bounded command/provenance/
  artifact plumbing evidence only; it is not 50-run scale evidence,
  controller promotion, broad-training evidence, normal-information
  performance, natural A20 performance, live-game validation, or final-agent
  evidence.
- T050 adds deterministic current-schema natural battle-start source-pool shard
  merge/finalization through `--merge-battle-start-pool-shards` and merged A20
  coverage reporting through `--merge-a20-battle-start-coverage`. Maintainer
  review passed 640 Windows tests, compileall, ruff, format check, task-doc
  checks, diff whitespace checks, focused merge/CLI/coverage tests, both
  CommunicationMod fixture smokes, the WSL pinned source verifier, a
  same-runtime WSL PyTorch/native probe, retained artifact hash checks, and
  deterministic regeneration of the baseline source merge, baseline coverage
  merge, and full reachability report hashes from retained shards. The
  retained artifact root is
  `artifacts/t050-root-prior-reachability-scaleup-pr/`, with retention
  manifest sha256
  `74a7390d40e6ffa5c993ed23a9ac782b9267403cef7de92dda31719683b6ea49`; the
  retained regeneration script now defaults to the stable post-merge repo path
  and records the review worktree only as provenance/override evidence. The
  accepted scale run used matched seeds `1..50`, A20, step cap 500,
  `stochastic-v1` with non-combat seed 42050, native root budget 20, 16
  source shards/workers and 16 coverage/restore workers per arm. Baseline
  Oracle search produced 248 Act-1 starts, 198W/50L, and one Act-1 Boss start;
  post-search `model_guided_oracle_search_v2` produced 247 Act-1 starts,
  197W/50L, and one Act-1 Boss start; root-prior guided search produced 236
  Act-1 starts, 186W/50L, and zero Boss starts. No arm reached Act 2 or later,
  restore/context checks matched all records, and the T009 gate remained open
  only for Act 1 while closed for Acts 2--4. This is source-generation and
  reachability scale evidence only; it is not controller promotion,
  broad-training evidence, normal-information performance, natural A20
  performance, live-game validation, or final-agent evidence.
- T051 adds the broader matched A20 search-controlled source-collection
  evidence using the T050 merge/reporting path. Maintainer review passed 641
  Windows tests, compileall, ruff, format check, task-doc checks, diff
  whitespace checks, both CommunicationMod fixture smokes, focused
  reachability/CLI tests including a corrupted source-run-summary fail-closed
  regression, the WSL pinned source verifier, a py313 torch/native
  same-runtime probe, retained artifact hash checks, and a full retained
  reachability report rebuild attempt that completed with no command problems.
  The retained artifact root is
  `artifacts/t051-search-controlled-later-act-source-collection-pr/`, with
  retention manifest sha256
  `e2c83ef4892ff74129c3649dc4b1dd52493777b74339f094c5c804e2bbb3d0b9` and
  reachability report sha256
  `0e001e38b3a7587dd7f1845a6d3fcfc6541f2056dffd8e4aaa5206053adc3877`. The
  accepted scale run used matched seeds `1..1000`, A20, step cap 500,
  `stochastic-v1` with non-combat seed 42050, native root budget 20,
  `highest_mean` root selection, and 16 source shards/workers plus 16
  coverage/restore workers per arm. Baseline Oracle search produced 4,774
  battle starts, 32 Act-1 Boss starts, and no later-act starts; post-search
  `model_guided_oracle_search_v2` produced 4,771 battle starts, 34 Act-1 Boss
  starts, and 3 Act-2+ starts from 1 source run; root-prior guided search
  produced 4,548 battle starts, 22 Act-1 Boss starts, and 2 Act-2+ starts from
  1 source run. Restore and coverage command status passed for all arms, but
  the T009 broad-training gate remained closed. This is source-generation and
  reachability evidence only; it is not controller promotion, broad-training
  evidence, normal-information performance, natural A20 performance,
  live-game validation, or final-agent evidence.
- T052 adds the retained 93-record T051 Boss/later-act fixed diagnostic cohort
  and restored-battle comparison evidence under
  `artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/`. Maintainer
  review accepted the fixed cohort sha256
  `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`, the
  root-prior comparison sha256
  `0cc496e6bddff0e5cecaee5e804d9ff4c89b2498093cb59d3feffbd245bb4a64`, and
  result summary sha256
  `1207ae0e93fa6f857add7dbaa553c3d92c86391772e842ce1e6bd08b55d97fe5`. The
  comparison used equal native root budget 20 and 16 workers/shards. Baseline
  Oracle search and post-search `model_guided_oracle_search_v2` both produced
  4W/89L overall; root-prior guided search produced 3W/90L. Boss-only tied at
  1W/87L for all arms, while the Act-2+ subset was 3W/2L for baseline and
  post-search versus 2W/3L for root-prior. This is restored-battle diagnostic
  evidence only, not controller promotion or broad-training evidence.
- T053 adds the offline
  `t053-root-prior-allocation-failure-analysis-v1` workflow and report over
  the retained T052 artifacts. Maintainer review accepted report sha256
  `73a1d153adce9782cafaf1caddb3fa0ddad2fafe33e653d88808875397832a73`. The
  analysis found four disagreement records out of 93: indices `53`, `54`,
  `55`, and `87`. Records `53` and `55` were harmful root-prior losses,
  record `54` was terminal-HP-only/no-op, and record `87` was beneficial for
  root-prior. Exact step-level selected-action comparison remains unavailable
  because T052 telemetry lacks compatible selected action identities for all
  arms. The recommended next task is a guardrailed root-prior allocation repair
  experiment; T053 itself does not implement repair, promotion, live-game
  validation, broad training, or normal-information search.
- T054 adds `guardrailed_root_prior_guided_oracle_search_v1` and the
  `t054-guardrailed-root-prior-repair-report-v1` workflow over the retained
  T052 Boss/later-act fixed diagnostic cohort. Maintainer review accepted
  report sha256
  `91f9e9b63b2f104a092a2a48dc1a3c4cc279f63300b0e097ba116fd80e601fec`,
  comparison sha256
  `b588d1d0f648c07d2fbcb1067a9fdea385ce90676e6c3ecd0eda6f61dbc7627d`,
  and retention manifest sha256
  `61ea735d6c1a31be14ecdc9daad433b18e2c0445ee42f474a2e55dcca957e5d3`
  under
  `artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/`.
  The comparison used all 93 T052 records, equal native root budget 20,
  `highest_mean` root selection, and 16 WSL workers/shards. Baseline Oracle
  search, post-search `model_guided_oracle_search_v2`, and the guardrailed
  variant each produced 4W/89L overall; existing root-prior produced 3W/90L.
  On the four T053 disagreement records, the guardrailed variant produced
  3W/1L versus 2W/2L for existing root-prior. Boss-only improved to 2W/86L for
  the guardrailed arm versus 1W/87L for the other arms. Act-2+ remained 2W/3L
  for both existing and guardrailed root-prior, behind baseline/post-search at
  3W/2L. T054 recommended exactly one next task: scale the repaired variant.
  This remains restored-battle Oracle-like diagnostic evidence only, not
  controller promotion, complete-run reachability evidence, natural A20
  performance, broad-training readiness, live-game validation, or
  normal-information strength.
- T055 adds the
  `t055-guardrailed-root-prior-scale-validation-report-v1` workflow and
  retained four-arm scale-validation artifacts under
  `artifacts/t055-guardrailed-root-prior-fixed-cohort-scale-validation-pr/`.
  Maintainer review accepted regenerated stable-path report sha256
  `0e365f76fcde88d81917b587ae162843488527dd7b422a43998ab24a069cae04`,
  retention manifest sha256
  `f1f7692fdc9baca2218dcc68e954e0e0ebdc322bf27dc2654387b52fb8cde787`,
  current T046-compatible comparison sha256
  `1580968ffd592433d838c3dde780148e43a33c145079f8a332dfcb1a2a9b0246`,
  and assist_0 runs1000 comparison sha256
  `7a96015ad103cb6c06d092fd2bf03d7b194cef12d3053808bc444b649ae994da`.
  The current 8-record cohort used 8 WSL workers/shards over record range
  `0:8` and produced baseline 5W/3L, post-search 5W/3L, existing root-prior
  6W/2L, and guardrailed root-prior 6W/2L. The assist_0 21-record cohort used
  16 WSL workers/shards over record range `0:21` and produced baseline
  11W/10L, post-search 11W/10L, existing root-prior 13W/8L, and guardrailed
  root-prior 12W/9L. The labeled aggregate was baseline 16W/13L, post-search
  16W/13L, existing root-prior 19W/10L, and guardrailed root-prior 18W/11L.
  T055 therefore marks the guardrailed variant as regressed by one win versus
  existing root-prior on the assist_0 cohort and aggregate, and its exactly
  one recommendation is to abandon the guardrail path. This remains
  restored-battle Oracle-like diagnostic evidence only, not controller
  promotion, complete-run reachability evidence, natural A20 performance,
  broad-training readiness, live-game validation, normal-information strength,
  or final-agent evidence.
- T056 adds `t056-post-t055-root-prior-path-selection-report-v1` and an
  offline report workflow over retained T048/T050/T051/T052/T053/T054/T055
  artifacts. Maintainer review accepted regenerated stable-path report sha256
  `f5db1a5f6bcdd99f78051f7b99ad970c76099add59d9655c6cd2abdd2ad6e26e`
  with byte count `1411522` under
  `artifacts/t056-post-t055-root-prior-path-selection-pr/`. The command
  verified 13 explicit input artifacts, including the T055 retention manifest,
  and failed closed on a pretty-printed wrong-schema T055 manifest regression.
  The report keeps T048 positive fixed-cohort evidence, T052/T053 later-act/
  Boss evidence, T054 repair evidence, T055 guardrail scale evidence, and
  T050/T051 complete-run reachability evidence separate. It closes the
  T054/T055 guardrail branch, rejects guardrailed root-prior complete-run
  reachability, and recommends exactly one non-guardrail next path:
  `existing-root-prior allocation/telemetry diagnostic`. This remains offline
  synthesis over Oracle-like restored-battle and source-reachability evidence,
  not controller promotion, complete-run reachability improvement evidence,
  natural A20 performance, broad-training readiness, live-game validation,
  normal-information strength, or final-agent evidence.
- T057 adds
  `t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1` and an
  offline report workflow over the accepted T056 report plus retained
  T048/T052/T053/T055 artifacts. Maintainer review accepted regenerated report
  sha256
  `52c6742e9a578381e38cd66babe86363c97fc46e7fee374770427de17edf3c88`
  with byte count `3739962` under
  `artifacts/t057-existing-root-prior-allocation-telemetry-diagnostic-pr/`.
  The command verified nine explicit input artifacts, summarized 122 retained
  existing-root-prior records and 2087 existing-root-prior decisions, and kept
  T048 positive fixed-cohort evidence, T052/T053 later-act/Boss evidence, and
  T055 guardrail-closure context separate. It found selected-action exact
  comparison infeasible for all retained records, with 0 available and 122
  unavailable records. The taxonomy counted 4 beneficial allocation signals, 2
  harmful allocation signals, 101 no-outcome-change records, 15
  terminal-HP-only changes, 1 distribution-specific conflict, and 122
  telemetry-insufficient records. T057 selected exactly one next path:
  `root-prior selected-action telemetry instrumentation or replay diagnostic`.
  This remains offline diagnostic evidence only, not controller promotion,
  root-prior complete-run reachability evidence, natural A20 performance,
  broad-training readiness, live-game validation, normal-information strength,
  or final-agent evidence.
- T058 adds
  `t058-root-prior-selected-action-telemetry-diagnostic-report-v1` and
  selected-action identity telemetry for restored-battle search comparisons.
  Maintainer review accepted the main-retained report sha256
  `ffadf375902321888f25b6883c474f0060e6aa0e82c2102fb3e3afd29ae78a04`
  with byte count `8672745` and retention manifest sha256
  `faf3dacc6c7d887aae3ab8f6878aa67ec1f47edabd071178e70b03f29584172f`
  with byte count `18891` under
  `artifacts/t058-root-prior-selected-action-telemetry-replay-pr/`. The
  retained comparison artifacts are T048 current sha256
  `f6c316e50121a118fdddf6921b38cb05f81cbc3e3024cf543eab3f9dfb091255`,
  T048 assist_0 sha256
  `abcf6ae352e690e4ef1131485ae71d06f1be987a2680cd15ba1bd0f9215b2965`,
  and T052 Boss/later-act sha256
  `c6c27c1e554eb6b5211d2d4591ee5b9a7998fc0b7968c02df459a0d009513bbe`.
  The report verified nine explicit input artifacts, found selected-action
  identity available for all 122 retained T048/T052 records, kept exact
  all-arm step-level selected-action comparison feasible for every retained
  record, and reported exact full-battle path comparison for 11 records. It
  found first selected-action divergence between existing root-prior and both
  baseline and post-search arms on all 122 records, counted 2 harmful
  selected-action divergence records, and selected exactly one next path:
  `root-prior allocation repair experiment`. This remains Oracle-like
  restored-battle diagnostic evidence only, not allocation repair evidence,
  controller promotion, root-prior complete-run reachability evidence, natural
  A20 performance, broad-training readiness, live-game validation,
  normal-information strength, or final-agent evidence.
- T059 adds `t059-root-prior-allocation-repair-report-v1` and the versioned
  `t059_root_prior_allocation_repair_oracle_search_v1` controller. Maintainer
  review verified the main-retained report sha256
  `6df13014e5468b9eb3c23d8e127be3559b5bc1529f46ce9d52ae96856fed7f89`
  with byte count `13449098` and normalized retention manifest sha256
  `e52428f98f5f961add5f0f8e95555d97f2720fb2e09c4a95bb38c39a4447f6b5`
  with byte count `44969` under
  `artifacts/t059-root-prior-allocation-repair-experiment-pr/`. The report
  verified 13 explicit input artifacts, compared all 122 retained records at
  equal native budget, and kept selected-action identity available for every
  record. The repair tied existing root-prior on both positive T048 cohorts
  (6W/2L versus 5W/3L on current and 13W/8L versus 11W/10L on assist_0) but
  also tied its T052 3W/90L regression and the T053 disagreement subset. Its
  single recommendation is to abandon allocation repair. This is
  `full_simulator_state_oracle_like` restored-battle diagnostic evidence only,
  not controller promotion, root-prior reachability, natural A20 performance,
  broad-training readiness, live-game validation, normal-information strength,
  or final-agent evidence.
- T061 adds `t061-a20-reachability-bottleneck-decomposition-v1`,
  `t061-restored-battle-budget-curve-v1`, and
  `t061-complete-run-factorial-report-v1`. Maintainer review accepted the
  retained bottleneck report sha256
  `bfc3bb2bbea81940a1ed0ab9affe7b4cea27a8922896209e927b0297190894ac`
  with byte count `44496958`, budget-curve report sha256
  `db22b90e497bb82e144e1fe43c94c8ffd99df2dfa1b1bcbc2dab9ea7597a3408`
  with byte count `10739122`, factorial report sha256
  `e652aa45ae3253e1c4018d7ceeb8571f197d7334e79a0304ec291d0b1fb41b41`
  with byte count `31340427`, and retention-manifest canonical self-hash
  `2fb5e329505b52541edbd7aa74b5fa2025e97276523ee341884538a4d7b3ef90`
  with byte count `6321` under
  `artifacts/t061-a20-reachability-bottleneck-decomposition/`. The restored
  curve evaluated the same 93 T052 records at budgets 20, 100, and 300 with 16
  shards/workers and obtained 4, 4, and 5 wins. The complete-run factorial ran
  256 shared A20 seeds in each of six battle-budget/non-combat-driver arms,
  1,536 terminal runs total, with 16 shards/workers, zero failures, and zero
  truncations. Under `expert_non_combat_v1`, increasing battle budget from 20
  to 300 increased matched Act-2 entry by `0.02734375`, bootstrap 95% CI
  `[0.0078125, 0.0546875]`; no arm reached Act 3, Act 4, or the Heart. T061
  therefore selected exactly T062. This is
  `full_simulator_state_oracle_like` diagnostic evidence only, not a new search
  algorithm, controller promotion, natural A20 strength, broad-training
  readiness, live-game validation, normal-information strength, or final-agent
  evidence.
- T062 adds the versioned `battle_search_v2_oracle_like_v1` controller surface
  with baseline, tree-internal policy-prior, learned-leaf-value, and combined
  ablations. It is accepted on `main` at merge commit
  `b01a83e1ec436410945e8037add301d6f952a712` with native integration commit
  `3cb9ebecb87c38044b34aa0e013d42b222a04087`. The retained cost-only
  calibration evidence is under
  `artifacts/t062-battle-search-v2-minimal-surface/calibration/native-prior-fix-3cb9ebe/`;
  its 111-artifact retention manifest is schema
  `t062-battle-search-v2-retention-manifest-v3`, 99618 bytes, sha256
  `dfac7d7660517cee65e311a8d1d2b6fa2d82ac7e26001b8da6ce28150e04ba12`.
  On deterministic T052 indices `0:16` with 16 explicit shards/workers,
  wall-clock ratios at guided budget 1 were `1.1077751075325` for
  `prior_only`, `1.026232129024169` for `value_only`, and
  `0.9140721130090935` for `prior_value`. `prior_only` was proven infeasible
  at the minimum legal budget, so T062 authorized no 93-record primary
  comparison or controller promotion and selected exactly T067. This is
  `full_simulator_state_oracle_like` cost-feasibility evidence only, not
  fixed-cohort outcome evidence, natural A20 performance, normal-information
  strength, live-game validation, or final-agent evidence.
- T067 adds versioned Search v2 cost attribution plus the
  `battle_search_v2_oracle_like_t067_cache_v1` exact public-node inference
  cache. It is accepted on `main` at merge commit
  `c65786e614d05c562eb78afaa61dbacff2f8f5bb`; the exact artifact-producing
  implementation commit is
  `ea47ee9df57b026bff96cf5c902f6a207b534cb1`. Semantic comparison on retained
  T052 record `0:1` matched policy/value outputs within `1e-6` and selected
  action identities exactly for `prior_only`, `value_only`, and
  `prior_value`. The reproduced `0:16` stage used 16 one-record
  shards/workers and recorded 866 cache lookups, 0 hits, 866 misses, and 0
  evictions. Budget-1 wall ratios were `1.164582194439893` for `prior_only`,
  `1.1487986693454382` for `value_only`, and `1.0240645131300026` for
  `prior_value`; the first two arms were proven infeasible at the minimum
  legal budget. T067 therefore failed all required calibration locks, ran no
  93-record outcome comparison, authorized no controller promotion, closed the
  exact-cache direction, and selected exactly
  `T068-native-boundary-batched-inference-feasibility`. The canonical retained
  root is
  `artifacts/t067-battle-search-v2-inference-cost-repair/reproduction-ea47ee9/`.
  Its 72-artifact retention manifest is schema
  `t067-battle-search-v2-retention-manifest-v2`, 43659 bytes, sha256
  `2119e36bccff86fd65f00474177d11bb222a05303651dc18423de7f1174d35da`;
  indexed artifacts total 77,759,244 bytes. The six authoritative regeneration
  commands prepare an exact detached source checkout and fresh output root,
  contain no disposable `.claude/worktrees` dependency, and were executed
  end-to-end during review. This remains `full_simulator_state_oracle_like`
  cost-feasibility evidence only, not fixed-cohort outcome evidence, natural
  A20 performance, normal-information strength, live-game validation,
  broad-training evidence, or final-agent evidence.
- T068 adds opt-in, default-off exact callback dependency traces plus versioned
  native-source, feasibility, semantic-equivalence, stage-execution, decision,
  and retention reports. It is accepted on `main` at merge commit
  `e70d047cdeb406ca223031460ef134201030a4de`; the exact artifact-producing
  implementation commit is
  `3dd14e31bbe310fef0b86d3fecf9ef203e67a411`. The pinned native commit remains
  `3cb9ebecb87c38044b34aa0e013d42b222a04087`. Semantic comparison on retained
  T052 record `0:1` preserved request occurrence order, selected-action
  identity, policy/value outputs within `1e-6`, traversal, simulator-step,
  chance/RNG, and terminal semantics for all three guided arms. The exact
  `0:16` audit used 16 one-record shards/workers, completed in 375 seconds, and
  recorded 207 `prior_only`, 261 `value_only`, and 398 `prior_value` requests.
  Every request was a synchronous singleton; no arm had an exact
  simultaneously-ready batch of size two or greater. Feature encoding consumed
  46,012.216903999724 ms, 48,498.62396400033 ms, and 63,462.21188099877 ms
  respectively, compared with 5,298.554254999942 ms, 4,038.125492999143 ms,
  and 2,507.4573129997475 ms of model forward time. T068 therefore correctly
  implemented no production batch boundary, ran no calibration or 93-record
  outcome comparison, authorized no promotion, closed native-boundary
  batching, and selected exactly
  `T069-public-node-feature-encoding-projection-feasibility`. The canonical
  retained root is
  `artifacts/t068-native-boundary-batched-inference-feasibility/reproduction-3dd14e3/`.
  Its 97-artifact retention manifest is schema
  `t068-native-boundary-retention-manifest-v1`, 65390 bytes, sha256
  `bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678`;
  indexed artifacts total 4,598,645 bytes and independently matched every
  published path, hash, size, and schema. This remains
  `full_simulator_state_oracle_like` cost-feasibility evidence only, not
  fixed-cohort outcome evidence, natural A20 performance, normal-information
  strength, live-game validation, broad-training evidence, or final-agent
  evidence.
- T069 adds one opt-in, default-off search-scope public-context feature
  projection while preserving the accepted unprojected scorer path. It is
  accepted on `main` at merge commit
  `db9157fc5e4c951b92b92f6689b5358091f09f7d`; the exact artifact-producing
  implementation commit is
  `46a5695e8921bdc62c2c5d6ef2e61c62b6b40ba2`. Semantic comparison on retained
  T052 record `0:1` matched complete scorer inputs exactly, policy/value outputs
  within `1e-6`, selected-action identities, traversal, simulator steps,
  chance/RNG behavior, and terminal fields for all guided arms. The paired
  `0:16` stage used 16 one-record shards/workers and matched all 866
  occurrence-safe scorer requests exactly. Measured search-wall reductions
  were `59.95948131507198%` for `prior_only`, `63.98741408672505%` for
  `value_only`, and `66.69862645569734%` for `prior_value`; all published
  material-improvement gates passed. Eighteen independent calibration
  candidates then locked wall-clock budgets `1/1/2` and simulator-step budgets
  `86/408/384` for `prior_only/value_only/prior_value`. The terminal
  simulator-step ratios were `1.0125363964066467`,
  `0.9773734594558252`, and `1.0430705896347172`. Every candidate used
  records `0:16`, 16 shards/workers, exact source identities, and zero failed
  workers. T069 therefore selected Case A and exactly
  `T062-original-93-record-outcome-comparison`, implemented no further
  cost-repair path, ran no 93-record outcome aggregation, and made no promotion
  claim. The stable retained roots are
  `artifacts/t069-public-node-feature-encoding-projection-feasibility/source-46a5695/`
  and
  `artifacts/t069-public-node-feature-encoding-projection-feasibility/reproduction-46a5695/`.
  The `t069-retention-manifest-v1` file is 327765 bytes with sha256
  `cb34f8c0c4ce00f14e424120566a09a1d666051e6effc9cd39e77d678df9dc76`;
  it indexes 1,301 artifacts totaling 1,004,285,022 bytes. Maintainer review
  independently matched every indexed path, size, and hash, validated all 19
  substantial stages, and rebuilt the pinned native source. This remains
  `full_simulator_state_oracle_like` semantic/cost evidence only, not
  fixed-cohort outcome evidence, natural A20 performance, normal-information
  strength, live-game validation, broad-training evidence, or final-agent
  evidence.
- T070 was accepted from pull request `#67` against approved specification
  commit `684f53f2f24881a10146387632797eaac3b3fd46`. Its final reviewed head is
  `40e062fdef37f96f5c5d1f19579ff25f4e7623cc`, and its `main` merge commit is
  `5c27c8caf4fe8f15603b3737be33c097be03a3c7`. T070 pins native commit
  `fee272f1ae21c283ad2161f55293cfe6d714134a`, exposes its read-only
  `battle_search_v2_with_tree_geometry` companion through the adapter, and
  leaves the existing Search v2 API and primary path unchanged. The exact
  artifact-producing STSRL commit is
  `ca8da8e4183798daf3c310566ede74daf90822aa`; Stage 0 used the matching
  CPython 3.13 extension with sha256
  `37853df3b51624a5f1a22fc5915db9a2c8d43d681638e97880018a58892bf38a`.
  All ten 93-record primary stages and six 16-record high-budget stages used
  the published 16 workers and ranges, returned zero worker, restore, mapping,
  checkpoint, missing-value, fallback, controller, truncation, or
  mixed-provenance failures, and passed the frozen-identity audit.

  The equal-nominal overall outcomes were `4/6/1/2` wins for
  `baseline/prior_only/value_only/prior_value`; equal-nominal `prior_value`
  regressed by two wins and had mean paired terminal-HP delta `-0.319` among
  outcome ties. Simulator-step-normalized outcomes were also `4/6/1/2`, with
  `prior_value` native-step ratio `0.849` rather than the required 5% match.
  Wall-clock-normalized outcomes were `4/2/4/1`, with `prior_value` wall ratio
  `1.384` rather than the required 10% match. The original T062 primary
  promotion gate therefore failed.

  On the frozen high-budget subset, baseline wins at budgets `100/400/1600`
  were `2/3/3`, while `prior_value` wins were `2/2/2`. Between
  `prior_value@100` and `prior_value@1600`, selected root actions changed on
  `8/16` records, root visit leaders changed on `6/16`, and first-root median
  maximum expanded depth grew from `4` to `8`, so
  `budget_100_not_sufficient=true`. The paired win delta remained `0/16`, and
  `prior_value@1600` regressed by one win against `baseline@1600`, so
  `high_budget_guidance_signal=false`. The terminal decision is Case C with
  exactly one planner recommendation, `T064 simulator-generated later-act
  curriculum`; no successor was published.

  Stable ignored evidence lives under
  `artifacts/t070-search-v2-outcome-budget-sufficiency/source-ca8da8e4183798daf3c310566ede74daf90822aa/`
  and
  `artifacts/t070-search-v2-outcome-budget-sufficiency/reproduction-ca8da8e4183798daf3c310566ede74daf90822aa/`.
  The primary, curve, geometry, decision, and stage-inventory report hashes are
  respectively `f02c53aef2aff805cdf83779d2ca9984cd4d48fedcb8814c544036dfbd18b067`,
  `49490b92f44d54907da5a25a5eb46e6f8b08361a47255622ac5dd1433b94f733`,
  `c62e745f107a00b06ce3b48098bf0178c5ebba150550ce9b4985e57e46dcbb1a`,
  `80afc3faa4a3369f1ca86abb4fd748eb5dd4cc22e1ad9c6335cc0024ebce30c9`,
  and `bfedf063291cfee32205c5604c2e40acdd56c471f8aa0555e7651d3b5f044795`.
  Retention manifest sha256
  `cc732f44ffb17cbc7ed9c08c9e664e5caa0be33a6cf7bce86c02eaea772d0ac0`
  indexes 897 files totaling 1,596,280,428 bytes; its 599-log index also
  retains transparent OOM and host-reboot attempts without mixing their shards
  into successful stages. Raw files remain retained until T070 is merged, the
  planner receives this maintainer report, and the named downstream retention
  condition closes. This is `full_simulator_state_oracle_like` fixed-cohort
  diagnostic evidence, not natural A20 performance, normal-information,
  live-game, broad-training, controller-promotion, or final-agent evidence.

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- interactive live-game or A20 performance validation for any controller;
- broad neural training on a scale/distribution-approved A20 dataset;
- model-guided search performance improvement or controller promotion;
- accepted outcome-based Search v2 controller advancement;
- sufficient Boss/later-act A20 source coverage for broad teacher/checkpoint
  refresh or broad training;
- root-prior allocation repair, root-prior guided complete-run reachability
  improvement evidence, or root-prior controller promotion;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The task
index is the canonical source for task lifecycle state; this section is a
snapshot of the current milestone and next work on the latest reviewed `main`.

The completed M1 synthesis is recorded in
[`m1_model_guided_search_sandbox_synthesis.md`](m1_model_guided_search_sandbox_synthesis.md).
It summarizes the merged telemetry, checkpoint inference, calibration,
controller, and fixed-comparison evidence from T025--T029. The synthesis
concludes that M1 succeeded as Oracle-like search plumbing but did not show
controller improvement: the accepted T029 smoke comparison tied baseline
Oracle search at five wins and three losses on eight restored A20 battles
while adding 120 checkpoint model calls for the model-guided controller.

T031, T036, T037, T039, T032, and T035 are complete. T031 found healthy
artifacts and restore evidence but no Boss or later-act starts. T036 rebuilt
the search-controlled collection path on current schemas while preserving the
battle/non-combat split, but its accepted 10-run smoke arms also reached no
Boss or later-act starts. T037 recovered the historical Boss/Act2 signal on
current schemas, and T039 converted that evidence into the durable source
coverage contract. T032 then ran the deliberately narrow diagnostic teacher,
trainer, checkpoint, and calibration refresh over that contract. T035 attempted
the deeper model-guided Oracle-like search experiment, but the accepted smoke
comparison tied the baseline and T028 outcomes.

The completed assisted source-generation batch follows the upstream guidance
supplied after T035. The maintainer role here was to publish and review bounded
tasks from that guidance, not to invent an alternate long-term plan.
T040 (`Expert Non-Combat Driver v1`), T041
(`Potion-enabled Oracle search repair`), T042
(`Assisted complete-run source generation`), and T033
(`Public context model-input encoder contract`) are complete. T043
(`Assisted teacher dataset and value/policy training`) and T044
(`De-assisted fixed-cohort evaluation`) are complete. The T044 result did not
show model-guided search improvement over baseline on the accepted smoke fixed
cohorts, so it closes the assisted batch as diagnostic evidence rather than a
promotion path. T045
(`Post-T044 failure analysis and guidance path selection`) is complete and
classified the immediate failure signals before another training,
native-search, or non-combat branch is published. T046
(`Native root-prior allocation search surface`) is complete. T047
(`Root-prior guided search comparison`) is complete. Its accepted one-record
smoke showed root-prior allocation can change a matched restored battle outcome
at equal native root budget, but it is not enough for promotion or broad
claims. T048 (`Root-prior guided search scale-up`) is complete. Its accepted
fixed-cohort scale-up improved over both baseline Oracle search and
post-search guidance on two matched cohorts, but it remains Oracle-like
restored-battle evidence rather than complete-run or promotion evidence. T049
(`Root-prior complete-run reachability probe`) is complete. Its bounded smoke
verified the checkpoint-guided complete-run collection path but did not reach
Boss or later-act starts in any arm, so it is not scale reachability evidence.
T050 (`Root-prior reachability scale-up and shard merge`) is complete. It added
deterministic source-pool shard merge/finalization support and ran the
50-terminal-run-per-arm scale pass, but no arm reached Act 2 or later.
T051 (`A20 search-controlled later-act source collection`) is complete. It ran
the 1,000-terminal-run-per-arm matched source collection and found scarce
later-act starts only in the post-search and root-prior guided arms, with
broad training still closed. T052
(`T051 Boss/later-act fixed-cohort diagnostic`) is complete. It consumed the
retained T051 natural Boss and Act-2+ starts, built a 93-record fixed
diagnostic cohort, and ran a 16-shard restored-battle comparison at equal
native root budget 20 and `highest_mean` root selection. The accepted result
was 4W/89L for baseline Oracle search, 4W/89L for post-search model-guided v2,
and 3W/90L for root-prior guided search overall; Boss-only tied at 1W/87L for
all arms, while the five-record Act-2+ subset was 3W/2L for baseline and
post-search versus 2W/3L for root-prior. There were no restore failures,
truncations, controller errors, or malformed root-prior allocation metadata.
T053 (`T052 root-prior allocation failure analysis`) is complete. It consumed
the retained T052 manifest, fixed cohort, root-prior comparison, and result
summary with accepted SHA-256 checks, wrote
`t053-root-prior-allocation-failure-analysis-v1` under
`artifacts/t053-t052-root-prior-allocation-failure-analysis-pr/`, and produced
report sha256
`73a1d153adce9782cafaf1caddb3fa0ddad2fafe33e653d88808875397832a73`.
It found four disagreement records out of 93: indices `53`, `54`, `55`, and
`87`. Records `53` and `55` were harmful root-prior losses where baseline and
post-search won; record `54` was terminal-HP-only with root-prior winning at
higher HP; record `87` was beneficial for root-prior where baseline and
post-search lost. T053 reported exact step-level selected-action comparison as
unavailable because T052 telemetry lacks compatible selected action identities
for all arms. T054
(`Guardrailed root-prior allocation repair experiment`) is complete. It
preserved the existing root-prior controller, added the versioned guardrailed
root-prior variant, ran the four-arm restored-battle comparison over the full
93-record T052 cohort, and wrote accepted artifacts under
`artifacts/t054-guardrailed-root-prior-allocation-repair-experiment-pr/`. The
accepted result was 4W/89L for baseline Oracle search, 4W/89L for post-search
model-guided v2, 3W/90L for existing root-prior, and 4W/89L for guardrailed
root-prior overall. On the T053 disagreement records, guardrailed root-prior
was 3W/1L versus 2W/2L for existing root-prior. Boss-only improved to 2W/86L
for guardrailed root-prior, but Act-2+ remained 2W/3L for both existing and
guardrailed root-prior versus 3W/2L for baseline/post-search. The single
recommended next task was T055, a fixed-cohort scale validation of the
repaired variant on the retained T048 cohorts. T055
(`Guardrailed root-prior fixed-cohort scale validation`) is complete. It ran
the four-arm comparison on the retained T048 current T046-compatible 8-record
cohort and assist_0 runs1000 21-record cohort, preserving equal native root
budget 20, root selection `highest_mean`, T048 cohort/checkpoint pairing, and
separate cohort reporting. The current cohort produced 5W/3L for baseline
Oracle search, 5W/3L for post-search model-guided v2, 6W/2L for existing
root-prior, and 6W/2L for guardrailed root-prior. The assist_0 cohort
produced 11W/10L for baseline, 11W/10L for post-search, 13W/8L for existing
root-prior, and 12W/9L for guardrailed root-prior. The 29-record aggregate was
16W/13L for baseline, 16W/13L for post-search, 19W/10L for existing
root-prior, and 18W/11L for guardrailed root-prior. T055's single
recommendation is to abandon the guardrail path; it does not authorize
guardrailed complete-run reachability, controller promotion, broad training,
live-game validation, natural A20 claims, or normal-information claims.
T056 (`Post-T055 root-prior path selection`) is complete. It consumed the
accepted retained evidence from T048, T050, T051, T052, T053, T054, and T055,
wrote `t056-post-t055-root-prior-path-selection-report-v1` under
`artifacts/t056-post-t055-root-prior-path-selection-pr/`, and produced report
sha256 `f5db1a5f6bcdd99f78051f7b99ad970c76099add59d9655c6cd2abdd2ad6e26e`.
The report command passed with no validation problems, closed the T054/T055
guardrail path, rejected guardrailed root-prior complete-run reachability, and
selected exactly one next path: `existing-root-prior allocation/telemetry
diagnostic`. The key unresolved diagnostic remains exact all-arm step-level
selected-action comparison in the T052/T053 telemetry.

The immediate external-fork follow-up is
[`lsmfttb/sts_lightspeed#7`](https://github.com/lsmfttb/sts_lightspeed/issues/7):
archive historical STSRL task branches after creating provenance tags, while
preserving `stsrl/main` as the sole active integration branch. This is
operational fork maintenance and does not block STSRL repository work.

The completed assisted source-generation batch is:

1. T040 implements `expert_non_combat_v1` as a seeded, stochastic A20
   heuristic source-generation driver and compares source coverage against
   `stochastic-v1` under the same Oracle-like battle controller.
2. T041 repairs the potion-enabled Oracle-like search root-mapping failure and
   reruns a no-potion vs potion-enabled fixed-cohort comparison.
3. T042 extends HP/potion/encounter assistance into complete-run continuation
   with explicit `assisted_run` distribution tags and assistance schedules.
4. T033 finalizes `public-context-model-input-v1`, a versioned public-context
   feature contract with explicit missingness, hidden-field firewall,
   assistance non-leakage, and checkpoint semantic validation.
5. T043 uses assisted source pools for decision-level Oracle teacher data and
   public student policy/value/resource diagnostics.
6. T044 evaluated whether assisted-data models help, or at least do not harm,
   search on low-assistance or unassisted fixed cohorts; the accepted smoke
   evidence tied the baseline for model-guided search and did not promote a
   controller.
7. T045 diagnoses why T044 did not improve outcomes and recommends the next
   guidance path before any larger training or native-search task is
   published. Its accepted smoke evidence favored native root-prior allocation
   as the primary next search path, while preserving assisted training and
   de-assisted distribution repair as secondary diagnostic follow-ups.

T058 (`Root-prior selected-action telemetry replay diagnostic`) made every
retained record's selected action auditable and authorized one bounded T059
allocation repair experiment. T059 completed that experiment with all 122
records available for comparison. The entropy-tempering repair preserved the
T048 positive cohorts but did not improve the T052 Act-2+/Boss or T053 harmful
evidence over existing root-prior allocation. The allocation-repair route is
therefore closed rather than promoted or extended into reachability.

T060's proposed 10,000-terminal-run natural A20 source-coverage scale-up was
cancelled before execution: it would have measured the same weak
policy-induced occupancy distribution more precisely without identifying its
cause. T061 replaced it with matched restored-battle and complete-run
interventions. The accepted result found a positive battle-budget effect on
Act-2 entry under `expert_non_combat_v1`, no Act-3/Act-4/Heart reachability,
and selected T062 as exactly one next task.

T062 (`Battle Search v2 Minimal Surface`), T067 (`Battle Search v2
Inference-Cost Repair`), T068 (`Native-Boundary Batched Inference
Feasibility`), and T069 (`Public-Node Feature-Encoding Projection
Feasibility`) are complete. T067 found 0 hits across 866 exact cache lookups.
T068 proved that all 207/261/398 guided callbacks were synchronous singletons.
T069 then proved one exact search-scope projection, materially reduced search
wall time in every guided arm, and locked all six cost configurations without
changing accepted scorer or search semantics. T070 is also complete. Its
primary outcome gate failed, its bounded diagnostic found the 100-simulation
budget insufficient without a high-budget guidance signal, and its Case C
decision recommends T064 to the planner without publishing it.

T064 is complete with `experiment_complete=true`, source adequacy and integrity
valid, no unmet acceptance criteria, and terminal `Case B`. Its assistance-
annealed curriculum tied the static mixture on both T044 model-guided cohorts,
improved `assist_hp50` raw-policy wins by one, tied seed 64001 on T052, and
regressed by one win at seed 64002 and on the Act-2+ subset. The accepted result
therefore does not promote the curriculum and recommends T065 to the planner.
No task is currently `READY`; that recommendation does not publish or authorize
T065. No further natural source scale-up is authorized by the
T062/T067/T068/T069/T070/T064 evidence alone.

T034 remains blocked on an explicit native simulator boundary for
public-consistent hidden-future sampling.

The adapter and captured-sample compatibility gate in
[`T013`](tasks/T013-live-communicationmod-runtime-adapter.md) is complete.
Simulator-only RL training does not depend on it. No trained or search
controller, nor any interactive real-game performance, has yet been validated.

## Code Quality And Maintenance Assessment

The implementation is in a usable post-foundation state: tests are broad,
artifact migrations are covered, optional PyTorch stays isolated behind the
`train` dependency group, project-level docs are maintainer-owned, and real
simulator gates run through WSL against the pinned source manifest.

No urgent correctness-driven cleanup is currently reported. The planner may
use the following maintenance assessment when deciding whether to propose
another research task. T019 removed the largest CLI routing hotspot:

- `src/sts_combat_rl/cli.py` is about 230 lines and now delegates parser
  construction, validation, path helpers, simulator policy construction, and
  lightspeed command routing to focused command/helper modules. The largest
  new routing modules are `commands/cli_parser.py` and
  `commands/lightspeed_cli.py`; this is acceptable as the first mechanical
  split and keeps behavior reviewable.
- Several simulator modules are intentionally feature-complete but large:
  `torch_policy_value.py`, `constructed_battle_start.py`,
  `fixed_battle_evaluation.py`, `features.py`, and `battle_start_pool.py` are
  each over 1,200 lines. Split only when a task can preserve current schemas
  and tests without changing behavior.
- `src/sts_combat_rl/sim/__init__.py` exports a broad compatibility surface.
  T019 added explicit export-surface regression tests, but future cleanup may
  still reduce accidental public API growth under a dedicated compatibility
  task.

The first cleanup pass is complete as
[`T019`](tasks/T019-codebase-mechanical-refactor.md). Remaining cleanup should
continue to be published as explicit maintenance tasks, not mixed into
model/search/data PRs. Suggested boundaries after T019 are:

1. Large-module split for T008/T009/T005 implementation files along schema,
   formatting, validation, and command-adapter boundaries.
2. Follow-up public export tightening for `sts_combat_rl.sim.__all__`, if T019
   keeps broad compatibility shims that should later be narrowed.

## Legacy Integration Reference

Commit `d56e10e` on `codex/integration-current` preserves a large body of
previously tested but unreviewed work. It combines many independent concerns
and therefore violates the one-task-one-branch rule.

It will not be merged wholesale and is not a development base. Each useful
capability is mapped to a focused task under [`tasks/`](tasks/README.md).
Implementers may consult that commit, but each PR must be independently
understandable, scoped, tested, and based on the latest `main`.

The branch remains untouched as a recovery reference until every mapped task
has been merged, rejected, or explicitly superseded.

## Environment

Real simulator work runs through WSL:

```text
checkout:      ~/stsrl-spikes/sts_lightspeed
system build:  ~/stsrl-spikes/sts_lightspeed/build-py
repository:    /mnt/d/DeadlycatCoding/STSRL
```

See [`sts_lightspeed_wsl_spike.md`](sts_lightspeed_wsl_spike.md) for commands
that are currently available on `main`. The canonical day-to-day source path is
the active `stsrl/main` fork integration branch pinned in
[`sts_lightspeed_source_manifest.json`](sts_lightspeed_source_manifest.json)
and verified by `scripts/verify_lightspeed_source.sh`. Runtime gates use
`/home/lsmft/stsrl-spikes/sts_lightspeed/build-py` rebuilt from that pinned
source.

Checkpoint-guided WSL gates have an additional runtime alignment requirement:
the exact WSL Python used for the gate must import both PyTorch and the active
`slaythespire` native extension, and that extension must expose the task's
required native APIs. See
[`sts_lightspeed_wsl_spike.md`](sts_lightspeed_wsl_spike.md) for the
same-runtime probe. As of the T048 review on 2026-07-02, the maintainer
machine has two relevant runtimes: system `python3` is Python 3.14.4 for the
ordinary `build-py` simulator gates, while checkpoint-guided T048 evidence used
`/home/lsmft/stsrl-spikes/py313-torch/bin/python` with the matching
`/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch` native build.
Do not mix a torch-capable interpreter with a `slaythespire` build compiled for
another CPython ABI. Source-verifier success does not by itself satisfy
checkpoint-guided runtime evidence.

Scale matters operationally. T037 exposed that a single-worker WSL
source-generation run is too slow and leaves host resources underused for
1,000-run evidence; T044 exposed the same risk for restored fixed-cohort
comparison runs. Future large or long-running WSL `sts_lightspeed`
source-generation, coverage, restore verification, teacher collection,
restored-evaluation, fixed-cohort comparison, or training-scale runs should be
sharded and executed with explicit parallel workers by default. The default
scale-worker target is the host logical CPU count, capped by shard count and
documented memory or simulator limits; on the current 16-logical-core
maintainer machine, use 16 workers for large WSL stages unless a lower-worker
resource or tooling reason is reported. This is a per-stage requirement:
source collection, coverage/restore gates, report rebuilding, teacher
collection, restored evaluation, and comparison stages each need a reported
worker/shard plan or an explicit single-worker reason. A `smoke` label does
not exempt a stage whose cohort size or expected wall-clock cost is already
substantial; the PR must report shard identity, worker count, seed/source-run
or cohort-record ranges, wall-clock cost, and any single-worker exception.
Single-worker WSL execution is reserved for small smoke tests, debugging,
non-simulator artifact aggregation, or a documented resource/tooling
constraint.
