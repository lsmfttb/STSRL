# Task Lifecycle Registry and Historical Archive

This compact archive is the single complete durable lifecycle registry for
published and landed tasks. It keeps every task ID, lifecycle state, primary
contract link, dependency summary, and terminal/provenance note from the former
full task index. The linked task documents remain authoritative for complete
scope, evidence, and acceptance meaning. The registry intentionally does not
duplicate long experiment reports.

| ID | State | Task contract | Depends on | Historical lookup |
|---|---|---|---|---|
| T001 | DONE | [Main quality baseline](T001-main-quality-baseline.md) | none | formatting and lint cleanup |
| T002 | DONE | [Controlled-run foundation](T002-controlled-run-foundation.md) | T001 | controller contracts and controlled run |
| T003 | DONE | [Artifact provenance foundation](T003-artifact-provenance-foundation.md) | T002 | artifact versioning and decision records |
| T004 | DONE | [Battle-start checkpoint pool](T004-battle-start-checkpoint-pool.md) | T002, T003, T010 | checkpoint restore and battle-start pool |
| T005 | DONE | [Fixed structural battle evaluation](T005-fixed-battle-evaluation.md) | T004 | fixed evaluation set and runner |
| T006 | DONE | [Oracle search teacher pipeline](T006-oracle-search-teacher.md) | T003, T004, T005, T017 | search policy, teacher, and dataset |
| T007 | CANCELLED | [Complete public run history (superseded)](T007-complete-public-run-history.md) | none | replaced by T014--T016 |
| T008 | DONE | [A20 constructed battle supplements](T008-a20-constructed-supplements.md) | T003, T004, T016, T017 | battle-start transforms and HP policy |
| T009 | DONE | [PyTorch search-guidance model](T009-pytorch-search-guidance.md) | T003, T006, T011, T012, T016, T018 | optional train dependency and policy/value model |
| T010 | DONE | [Stochastic non-combat driver](T010-stochastic-non-combat-driver.md) | T002 | non-combat policy and native visible actions |
| T011 | DONE | [Tactical feature contract v2](T011-tactical-feature-contract-v2.md) | T003 | feature and model-input upgrades |
| T012 | DONE | [Structured battle resource outcomes](T012-structured-resource-outcomes.md) | T003, T004, T010, T016, T017 | persistent resource snapshots and outcomes |
| T013 | DONE | [Live CommunicationMod runtime adapter](T013-live-communicationmod-runtime-adapter.md) | T003, T011 | trained/search controller deployment |
| T014 | DONE | [Native public projection capability](T014-native-public-projection-capability.md) | T002, T003, T004, T010, T011 | native public projection and action parity |
| T015 | DONE | [Public run context and controlled history](T015-public-run-context-and-controlled-history.md) | T002, T003, T004, T011, T014 | sanitized context and ordered history |
| T016 | DONE | [Public-context artifacts, replay, and audit](T016-public-context-artifacts-replay-and-audit.md) | T003, T004, T005, T011, T014, T015 | migrations, replay, and coverage audit |
| T017 | DONE | [Stable sts_lightspeed source integration](T017-stable-lightspeed-source-integration.md) | T004, T010, T014, T016 | external source manifest and verifier |
| T018 | DONE | [Native terminal resource identity surface](T018-native-terminal-resource-identity.md) | T012, T017 | native terminal potion/deck/relic/key identities |
| T019 | DONE | [Codebase mechanical refactor](T019-codebase-mechanical-refactor.md) | T001--T018 except T007 | CLI decomposition and export cleanup |
| T020 | DONE | [sts_lightspeed fork maintenance line](T020-sts-lightspeed-fork-maintenance.md) | T017 | single active fork integration branch |
| T021 | DONE | [A20 battle-start coverage measurement](T021-a20-battle-start-coverage-measurement.md) | T004, T005, T008, T009, T010, T012, T016, T017, T018, T020 | natural/constructed coverage and training gates |
| T022 | DONE | [A20 Oracle teacher dataset report](T022-a20-oracle-teacher-dataset-report.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021 | teacher coverage and source linkage |
| T023 | DONE | [A20 Oracle teacher dataset scale-up](T023-a20-oracle-teacher-dataset-scale-up.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021, T022 | teacher scale-up and budget stability |
| T024 | DONE | [Oracle teacher search-guidance training bridge](T024-oracle-teacher-search-guidance-training-bridge.md) | T003, T004, T006, T009, T011, T012, T016, T017, T018, T020, T021, T022, T023 | trainer input and diagnostic checkpoint |
| T025 | DONE | [Search telemetry baseline](T025-search-telemetry-baseline.md) | T005, T006, T009, T017, T020, T024 | shared search telemetry and cost reporting |
| T026 | DONE | [Guidance checkpoint inference contract](T026-guidance-checkpoint-inference-contract.md) | T009, T011, T016, T018, T024 | checkpoint scorer contract |
| T027 | DONE | [Teacher guidance calibration report](T027-teacher-guidance-calibration-report.md) | T026 | checkpoint-vs-teacher calibration |
| T028 | DONE | [Model-guided Oracle search controller](T028-model-guided-oracle-search-controller.md) | T025, T026, T027 | versioned Oracle-like search controller |
| T029 | DONE | [Fixed-cohort model-guided search comparison](T029-fixed-cohort-model-guided-search-comparison.md) | T025, T028 | equal-source/equal-budget comparison |
| T030 | DONE | [M1 model-guided search sandbox synthesis](T030-m1-model-guided-search-sandbox-synthesis.md) | T027, T029 | milestone synthesis and next task batch |
| T031 | DONE | [A20 coverage refresh and data gap report](T031-a20-coverage-refresh-data-gap-report.md) | T030 | post-M1 A20 coverage refresh |
| T032 | DONE | [A20 narrow teacher and checkpoint diagnostic refresh](T032-a20-teacher-checkpoint-refresh.md) | T039 | narrow source-contract diagnostic |
| T033 | DONE | [Public context model-input encoder contract](T033-public-context-encoder-contract.md) | T016, T030, T042 | public history/map/Boss encoder boundary |
| T034 | BLOCKED | [Public-consistent hidden-future sampler boundary](T034-public-consistent-hidden-future-sampler.md) | T033, native sampler support | normal-information hidden-future substrate |
| T035 | DONE | [Model-guided Oracle search v2](T035-model-guided-oracle-search-v2.md) | T032, T025, T028, T029 | deeper Oracle-like guidance |
| T036 | DONE | [A20 search-controlled reachability probe](T036-a20-search-controlled-reachability-probe.md) | T006, T017, T020, T025, T029, T031 | search-controlled reachability |
| T037 | DONE | [A20 search-controlled reachability scale-up](T037-a20-search-controlled-reachability-scaleup.md) | T017, T020, T036 | Boss/Act2 reachability scale-up |
| T038 | CANCELLED | [A20 source drift audit](T038-a20-source-drift-audit.md) | T037 | unnecessary after T037 recovered reachability |
| T039 | DONE | [Later-act/Boss source coverage contract](T039-later-act-boss-source-coverage-contract.md) | T037 | explicit source-coverage contract |
| T040 | DONE | [Expert Non-Combat Driver v1](T040-expert-non-combat-driver-v1.md) | T010, T016, T017, T025, T036, T037, T039, T035 | heuristic source-generation driver |
| T041 | DONE | [Potion-enabled Oracle search repair](T041-potion-enabled-oracle-search-repair.md) | T006, T017, T020, T025, T036, T037, T039 | potion root mapping repair |
| T042 | DONE | [Assisted complete-run source generation](T042-assisted-complete-run-source-generation.md) | T040, T041 | assisted-run distribution and coverage |
| T043 | DONE | [Assisted teacher dataset and value/policy training](T043-assisted-teacher-value-policy-training.md) | T042, T033 | assisted teacher data and student diagnostics |
| T044 | DONE | [De-assisted fixed-cohort evaluation](T044-de-assisted-fixed-cohort-evaluation.md) | T043 | low/no-assistance evaluation |
| T045 | DONE | [Post-T044 failure analysis and guidance path selection](T045-post-t044-failure-analysis.md) | T043, T044 | failure taxonomy and guidance path |
| T046 | DONE | [Native root-prior allocation search surface](T046-native-root-prior-allocation.md) | T045, T017, T020 | native root-prior allocation surface |
| T047 | DONE | [Root-prior guided search comparison](T047-root-prior-guided-search-comparison.md) | T046, T043, T044 | equal-source comparison |
| T048 | DONE | [Root-prior guided search scale-up](T048-root-prior-guided-scale-up.md) | T047 | matched-cohort scale-up |
| T049 | DONE | [Root-prior complete-run reachability probe](T049-root-prior-complete-run-reachability-probe.md) | T048, T036, T037 | complete-run reachability plumbing |
| T050 | DONE | [Root-prior reachability scale-up and shard merge](T050-root-prior-reachability-scaleup-and-shard-merge.md) | T049, T048, T036, T037 | sharded reachability scale pass |
| T051 | DONE | [A20 search-controlled later-act source collection](T051-a20-search-controlled-later-act-source-collection.md) | T050, T049, T048, T036, T037 | broader later-act source collection |
| T052 | DONE | [T051 Boss/later-act fixed-cohort diagnostic](T052-t051-boss-later-act-fixed-cohort-diagnostic.md) | T051, T050, T048, T047, T005 | restored-battle later-act diagnostic |
| T053 | DONE | [T052 root-prior allocation failure analysis](T053-t052-root-prior-allocation-failure-analysis.md) | T052, T047, T048, T051 | allocation failure analysis |
| T054 | DONE | [Guardrailed root-prior allocation repair experiment](T054-guardrailed-root-prior-allocation-repair-experiment.md) | T053, T052, T048, T047, T046, T043 | guardrailed repair experiment |
| T055 | DONE | [Guardrailed root-prior fixed-cohort scale validation](T055-guardrailed-root-prior-fixed-cohort-scale-validation.md) | T054, T048, T047, T046, T044, T043 | guardrail scale validation |
| T056 | DONE | [Post-T055 root-prior path selection](T056-post-t055-root-prior-path-selection.md) | T055, T054, T053, T052, T051, T050, T048 | allocation route closure |
| T057 | DONE | [Existing root-prior allocation telemetry diagnostic](T057-existing-root-prior-allocation-telemetry-diagnostic.md) | T056, T055, T053, T052, T048, T046, T043 | existing allocation telemetry |
| T058 | DONE | [Root-prior selected-action telemetry replay diagnostic](T058-root-prior-selected-action-telemetry-replay-diagnostic.md) | T057, T052, T048, T046, T043 | selected-action comparison |
| T059 | DONE | [Root-prior allocation repair experiment](T059-root-prior-allocation-repair-experiment.md) | T058, T052, T048, T046, T043 | bounded allocation repair closure |
| T060 | CANCELLED | [Expert non-combat natural source coverage scale-up](T060-expert-non-combat-natural-source-coverage-scaleup.md) | T059, T040, T050, T039 | fixed-policy scale-up cancelled |
| T061 | DONE | [A20 self-generated reachability bottleneck decomposition](T061-a20-self-generated-reachability-bottleneck-decomposition.md) | T059, T040, T050, T052 | battle-budget bottleneck and T062 selection |
| T062 | DONE | [Battle Search v2 minimal surface](T062-battle-search-v2-minimal-surface.md) | T061, T052, T043, T046 | internal policy/value surface; calibration exit |
| T063 | DRAFT | [Oracle-guided public battle learning](T063-oracle-guided-public-battle-learning.md) | T061, T062, T033 | simulator-only Oracle assistance |
| T064 | DONE | [Simulator-generated later-act curriculum](T064-simulator-generated-later-act-curriculum.md) | T033, T042, T043, T044, T052, T069, T070 | Case B; exposure order did not pass transfer gates |
| T065 | DONE | [Learned non-combat policy v1](T065-learned-non-combat-policy-v1.md) | T033, T040, T061, T064, T071, T074 | Case D; replay-equivalent cross-split duplicates |
| T066 | DRAFT | [Alternating joint policy improvement and natural scale gate](T066-alternating-joint-policy-improvement-and-natural-scale-gate.md) | T062, T063, T064, T065 | separate battle/non-combat policies |
| T067 | DONE | [Battle Search v2 inference-cost repair](T067-battle-search-v2-inference-cost-repair.md) | T062, T061, T052, T043 | exact cache preserved semantics; no cost gate |
| T068 | DONE | [Native-boundary batched inference feasibility](T068-native-boundary-batched-inference-feasibility.md) | T067, T062, T052, T043 | synchronous singleton audit; batching closed |
| T069 | DONE | [Public-node feature-encoding projection feasibility](T069-public-node-feature-encoding-projection-feasibility.md) | T068, T067, T062, T052, T043 | semantics-preserving projection and cost gate |
| T070 | DONE | [Battle Search v2 fixed-cohort outcome and budget-sufficiency audit](T070-battle-search-v2-fixed-cohort-outcome-and-budget-sufficiency-audit.md) | T069, T062, T052, T043 | Case C; no Search promotion |
| T071 | DONE | [Post-T064 experiment execution simplification](T071-post-t064-experiment-execution-simplification.md) | T019, T064 | execution/reuse ownership and detached control |
| T072 | DONE | [Retire closed root-prior experiment executors](T072-retire-closed-root-prior-experiment-executors.md) | T053--T059, T071 | historical executor retirement |
| T073 | DONE | [Forward surface health gate](T073-forward-surface-health-gate.md) | T019, T064, T067--T072 | forward ownership recovery |
| T074 | DONE | [Core decision/policy boundary repair](T074-core-policy-boundary-repair.md) | T019, T073 | policy/batching/control boundary repair |
| T075 | DONE | [Leakage-safe non-combat cohort repair](T075-leakage-safe-non-combat-cohort-repair.md) | T033, T040, T061, T064, T065, T071, T074 | exact selection then TARGET Case D |
| T076 | DONE | [Checkpoint restore branch-isolation repair](T076-checkpoint-restore-branch-isolation-repair.md) | T075, T017, T020 | native map aliasing repair |
| T077 | DONE | [T075 same-experiment continuation](T077-t075-same-experiment-continuation.md) | T075, T076 | inherited TARGET Case D |
| T078 | DONE | [Restored public-context fidelity repair](T078-restored-public-context-fidelity-repair.md) | T077, T076, T015, T016, T017, T020, T033 | state-160 restore fidelity repair |
| T079 | DONE | [Battle Search state-utilization bounds recovery](T079-battle-search-state-utilization-diagnostic.md) | T078, T070, T069, T062, T052, T043, T017, T020 | conservative bounds; `AMBIGUOUS` |
| T080 | DONE | [Battle value-target semantic alignment audit](T080-battle-value-target-semantics-audit.md) | T079, T070, T069, T062, T052, T043 | `VALUE_TARGET_SEMANTICS_UNRESOLVED` |
| T081 | DONE | [Scientific artifact eligibility gate](T081-scientific-artifact-eligibility-gate.md) | T043, T044, T047, T048, T050, T051, T052, T062, T070 | separate fail-closed integrity/eligibility gates |
| T082 | DONE | [T064 value-target semantic closure](T082-t064-value-target-semantic-closure.md) | T080, T081, T064, T043, T042 | `VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED` |
| T083 | DONE | [Battle Search v2 leaf-value target contract audit](T083-battle-search-v2-leaf-value-target-contract.md) | T082, T081, T064, T062, T070 | `NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED` |
| T084 | DONE | [Search v2 internal-leaf continuation-utility target generation](T084-search-v2-internal-leaf-target-generation.md) | T083, T082, T081, T064, T062, T070 | `LEAF_CONTINUATION_UTILITY_TARGETS_READY`; 960 rows |
| T085 | DONE | [Corrected Search v2 leaf-value repair and paired evaluation](T085-corrected-leaf-value-search-repair.md) | T084, T083, T082, T081, T064, T052, T042, T070 | `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`; bounded claim |
| T087 | DONE | [Dense Combat outcome diagnostics and blind trace audit surface](T087-dense-combat-outcome-diagnostics.md) | T005, T012, T016, T018, T052, T078, T081, T085 | `DENSE_COMBAT_DIAGNOSTICS_READY`; diagnostic only |
| T088 | DONE | [Classical Combat Search Baseline Tournament](T088-classical-combat-search-baseline-tournament.md) | T005, T012, T016, T018, T052, T062, T078, T081, T085, T087 | `STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED`; Search v2 @400 frozen |
| T089 | DONE | [Frozen-Search Self-Generated Non-Combat Policy Improvement](T089-frozen-search-self-generated-non-combat-policy.md) | T033, T040, T065, T075, T076, T078, T081, T085, T088 | `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED` |
| T090 | DONE | [Search-v2 Action-Utility Battle Student](T090-search-v2-action-utility-battle-student.md) | T033, T062, T078, T081, T085, T087, T088 | `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT` |
| T091 | DONE | [Battle Teacher Data-Surface Density Audit](T091-battle-teacher-data-surface-density-audit.md) | T011, T016, T025, T062, T078, T081, T087, T088, T090 | `ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED` |
| T092 | DONE | [Internal Search-State Teacher Data-Surface Gate](T092-internal-search-state-teacher-data-surface.md) | T011, T016, T017, T020, T025, T062, T078, T081, T087, T088, T090, T091 | `INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH`; 8/8 shards |
| T093 | DONE | [Internal-State Partial-Ranking Public Battle-Student Distillation Gate](T093-internal-state-partial-ranking-battle-student.md) | T011, T016, T025, T062, T078, T081, T087, T088, T090, T091, T092 | `INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT` |
| T094 | DONE | [A-Cohort Supervision Attrition Decision Audit](T094-a-cohort-supervision-attrition-decision-audit.md) | T052, T085, T087, T090, T092, T093 | `A_COHORT_CANONICALIZATION_LIMITING` |
| T095 | DONE | [Repeated-Public-State Oracle Aggregation Feasibility Audit](T095-repeated-public-state-oracle-aggregation-feasibility.md) | T033, T092, T094 | `EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE` |
| T096 | DONE | [Battle Public-Information Hidden-Future Sampler Pilot](T096-battle-public-information-hidden-future-sampler-pilot.md) | T014, T015, T016, T020, T034, T076, T078, T079, T095 | `NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT` |
| T097 | DONE | [Native Visibility Capability Source Acceptance](T097-native-visibility-capability-source-acceptance.md) | T017, T020, T096 | `NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED`; pin `d309170` |
| T098 | DONE | [T096 Public-Information Fidelity Re-entry](T098-t096-public-information-fidelity-reentry.md) | T096, T097 | `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`; pin `d309170` |
| T099 | DONE | [Native Particle-Search Bridge Source Acceptance](T099-native-particle-search-bridge-source-acceptance.md) | T017, T020, T096, T097, T098 | `NATIVE_PARTICLE_SEARCH_BRIDGE_CAPABILITY_ACCEPTED`; pin `97f59b6` |
| T100 | DONE | [Repository Information-Architecture Compaction](T100-repository-information-architecture-compaction.md) | T099, current governance | `REPOSITORY_INFORMATION_ARCHITECTURE_COMPACTED`; documentation only |
| T101 | DONE | [Bounded Particle-Count Convergence and Cost Diagnostic](T101-bounded-particle-count-convergence.md) | T004, T078, T081, T087, T088, T096, T098, T099, T100 | `SUPPORTED_COHORT_INSUFFICIENT`; N=2 admission attempted all 413 candidates (A/B/C 93/192/128), admitted 0; no canary/formal run or convergence result |
| T102 | READY | [Planner Review Routing and Maintainer Polling Protocol](T102-agent-planner-notification-protocol.md) | T100, T101, current governance | governance-only; capability-grounded exact Planner routing, durable PR response, active-turn polling, recoverable idempotent resume |

## Same-ID contract and amendment files

The following files are additional durable contracts or amendments, not
renumbered tasks. They remain linked here so every task-support document is
discoverable from the archive:

- T065: [agent scope documentation alignment](T065-agent-scope-documentation-alignment.md),
  [frozen execution statistics contract](T065-frozen-execution-statistics-contract.md),
  and [Non-Combat model input v1](T065-non-combat-model-input-v1.md).
- T087: [legacy T085 paired-report compatibility amendment](T087-legacy-t085-paired-report-compatibility-amendment.md),
  [minimal historical input dependency amendment](T087-minimal-historical-input-dependency-amendment.md),
  [reproducibility amendment](T087-reproducibility-amendment.md),
  [terminal monster-resolution semantics amendment](T087-terminal-monster-resolution-semantics-amendment.md),
  and [terminal monster telemetry amendment](T087-terminal-monster-telemetry-amendment.md).
- T102: [resume-operation identity amendment](T102-resume-operation-identity-amendment.md)
  and [active-set route-binding amendment](T102-route-binding-amendment.md).

T086 has no published task contract in this repository; the numbering gap is
intentional historical provenance, not a missing link to invent.
