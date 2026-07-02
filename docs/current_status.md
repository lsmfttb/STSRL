# Current Status

Last reviewed: 2026-07-02.

This document describes the latest `main` branch only. Results from local
artifacts, old branches, or unmerged pull requests do not count as implemented
capabilities.

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
reachability. T050 is now `READY` to add source-pool shard
merge/finalization support and run the 50-terminal-run-per-arm complete-run
reachability scale pass. T034 remains blocked on native public-consistent
hidden-future sampler support.

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
  `9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a`. Historical task-shaped fork
  branches are retained only as provenance, and the old ordered patch stack is
  retained only as retired provenance.

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
  and states that current native APIs do not accept model allocation hints or
  leaf values. This is a controller smoke entry point only, not a fixed-cohort
  comparison, normal-information result, live-game validation, broad-training
  result, or controller-strength claim.
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
  simulator steps, root mapping, truncation, and restore failures. Current
  native APIs still do not accept model allocation hints or leaf values. This
  is diagnostic comparison evidence only, not normal-information, live-game,
  broad-training, performance-improvement, or controller-promotion evidence.
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

- `573` tests pass on Windows Python as of this review. In an uninstalled
  checkout, set `PYTHONPATH=src` (or install the package) before invoking the
  CLI directly.
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
  `242344c57c17c784708a6f072c905febc3f96527`,
  initializes `json` and `pybind11`, imports `slaythespire.StepSimulator`, and
  asserts the current native capability inventory including
  `native_battle_search_root`, `native_terminal_resource_identity`, and
  `constructed_battle_start_transforms`.
  Missing-manifest and wrong-commit verifier
  checks fail nonzero. `/home/lsmft/stsrl-spikes/sts_lightspeed/build-py` was
  rebuilt from that pinned source and imports `slaythespire` from the rebuilt
  directory. The required WSL smoke, public-projection capability,
  public-context replay, and battle-training-readiness gates pass.
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

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- interactive live-game or A20 performance validation for any controller;
- broad neural training on a scale/distribution-approved A20 dataset;
- model-guided search performance improvement or controller promotion;
- scale-quality root-prior guided complete-run reachability improvement
  evidence or root-prior controller promotion;
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
T050 (`Root-prior reachability scale-up and shard merge`) is now `READY` to
add deterministic source-pool shard merge/finalization support and run the
50-terminal-run-per-arm scale pass before any assisted training repair or
non-combat ranker branch.

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

The published follow-up is T050, which will add source-pool shard
merge/finalization support and run the 50-terminal-run-per-arm root-prior
complete-run reachability scale pass before any assisted training repair or
non-combat ranker branch.

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

No urgent correctness-driven cleanup is required before publishing the next
research task. T019 removed the largest CLI routing hotspot:

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
