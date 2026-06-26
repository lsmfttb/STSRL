# Current Status

Last reviewed: 2026-06-26.

This document describes the latest `main` branch only. Results from local
artifacts, old branches, or unmerged pull requests do not count as implemented
capabilities.

## Current Goal

Build the foundations for an A20 battle agent. Search remains the intended
primary battle policy, and learned policies or values are expected to guide or
accelerate search. Non-combat decisions remain outside the trainable agent.

The published foundation, maintenance, and first research-measurement backlog
is complete: T001--T006 and T008--T028 are `DONE`, and T007 is `CANCELLED`
because it was superseded by T014--T016. The current published milestone is
M1: model-guided Oracle search sandbox. T029 is the current `READY` task.

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
  `242344c57c17c784708a6f072c905febc3f96527`. Historical task-shaped fork
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
  a compact sanitized public-run-context summary; scores state-action policy
  rows; predicts battle survival and terminal absolute current HP; and keeps
  structured terminal resource heads separate. Broad training is guarded by a
  fail-closed per-ascension/per-act scale and distribution gate that counts
  stable source identities rather than repeated sampled rows and cannot use A0
  coverage to satisfy A20 requirements. Named `smoke` and `narrow_curriculum`
  overrides may run diagnostic training but never mark broad training ready.
  Checkpoints use `torch-policy-value-checkpoint-v1`, include exact
  trainer-input SHA-256 artifact provenance, controller and information-regime
  summaries, target-source summaries, distribution/source/sampling counts,
  stable source identity summaries, and semantic contract validation on load.
  Raw policy/value diagnostics are reported separately; model-guided fixed
  search evaluation is currently `not_run`.
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
  T023 scale-up budget, verifies the manifest, teacher artifact, T022 report,
  and source-pool SHA-256 identities, restores source starts through the
  simulator adapter, rebuilds public tactical/model-input features, and emits
  current trainer-input v6 records with explicit `trainer-policy-target-v1`
  policy targets. Supported policy target kinds are
  `behavior_chosen_action_one_hot`, `oracle_teacher_action_one_hot`, and
  `oracle_soft_visit_distribution`. Teacher action, soft visit target,
  behavior action availability, selected model policy target, structured
  battle outcomes, public-context status, stable source identity, sampling
  component, and `full_simulator_state_oracle_like` evidence boundary remain
  separately serialized and reported. Optional PyTorch training now consumes
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
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests And Runtime Evidence

- `535` tests pass on Windows Python as of this review. In an uninstalled
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

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- interactive live-game or A20 performance validation for any controller;
- broad neural training on a scale/distribution-approved A20 dataset;
- fixed-cohort model-guided search comparison or performance improvement;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The
current published milestone is M1: model-guided Oracle search sandbox. Its
nearer target is to compare the current Oracle-like native search baseline
against the first versioned model-guided Oracle-like search controller on the
same fixed restored starts, with complete telemetry and no promotion claims.

The currently published `READY` task is:

1. [`T029`](tasks/T029-fixed-cohort-model-guided-search-comparison.md):
   compare baseline Oracle search and the merged T028 model-guided
   Oracle-like controller on identical restored starts with separate outcome
   aggregates and cost telemetry.

The rest of M1 is already specified but intentionally blocked:

- [`T030`](tasks/T030-m1-model-guided-search-sandbox-synthesis.md): milestone
  synthesis and next task batch, blocked on T029.

The immediate external-fork follow-up is
[`lsmfttb/sts_lightspeed#7`](https://github.com/lsmfttb/sts_lightspeed/issues/7):
archive historical STSRL task branches after creating provenance tags, while
preserving `stsrl/main` as the sole active integration branch. This is
operational fork maintenance and does not block STSRL repository work.

Recommended post-M1 task areas:

1. Model-guided search integration: use T024 teacher-targeted
   trainer/checkpoint provenance to connect T009 policy/value checkpoints to a
   versioned search controller, report compute/model-call telemetry, and
   compare against fixed cohorts without claiming promotion from raw model
   diagnostics.
2. Fixed A20 benchmark reporting: compare scripted/preferred, Oracle search,
   raw model, and model-guided search only after the relevant controllers and
   datasets exist, keeping natural-weighted, encounter-macro, and
   room-type-macro results separate.
3. Broader A20 coverage and data collection: use T021/T022/T023 reports to
   decide which natural, sampled, constructed, and teacher-data strata need
   more source coverage before broad training.
4. Normal-information search groundwork: specify the authoritative
   public-consistent hidden-future sampling boundary before any belief-search
   branch starts.
5. Additional maintenance cleanup beyond T019, if the first refactor leaves
   large modules or export surfaces difficult to review.

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
