# Task Index

Tasks are the executable specification for feature branches and pull requests.
Read [`../collaboration_workflow.md`](../collaboration_workflow.md) before
starting work.

The Active Backlog table below is the only authoritative source for task
lifecycle state. Individual task documents intentionally omit mutable
`Status:` lines; they define scope, acceptance criteria, and historical
disposition where needed. `current_status.md` and roadmap files may summarize
the current milestone, but they do not override this table.

New task content originates with the planner. For a new task, the planner creates
a fresh task branch and draft pull request, writes the complete specification and
proposed lifecycle changes there, and submits that exact head to the maintainer
for independent review. The maintainer does not proactively add successor tasks.
Implementers are maintainer-managed sub-agents and may start only after the
workflow's explicit implementation-authorization gate is satisfied.

## Active Backlog

| ID | Status | Task | Depends On | Legacy Reference Areas |
|---|---|---|---|---|
| T001 | DONE | [Main quality baseline](T001-main-quality-baseline.md) | none | formatting and lint cleanup |
| T002 | DONE | [Controlled-run foundation](T002-controlled-run-foundation.md) | T001 | controller contracts, controlled run, rollout executor |
| T003 | DONE | [Artifact provenance foundation](T003-artifact-provenance-foundation.md) | T002 | artifact versioning, decision records |
| T004 | DONE | [Battle-start checkpoint pool](T004-battle-start-checkpoint-pool.md) | T002, T003, T010 | checkpoint restore, battle-start pool |
| T005 | DONE | [Fixed structural battle evaluation](T005-fixed-battle-evaluation.md) | T004 | fixed evaluation set and runner |
| T006 | DONE | [Oracle search teacher pipeline](T006-oracle-search-teacher.md) | T003, T004, T005, T017 | search policy, teacher, search dataset |
| T007 | CANCELLED | [Complete public run history (superseded)](T007-complete-public-run-history.md) | none | replaced by T014--T016 |
| T008 | DONE | [A20 constructed battle supplements](T008-a20-constructed-supplements.md) | T003, T004, T016, T017 | battle-start transforms and approximate HP policy |
| T009 | DONE | [PyTorch search-guidance model](T009-pytorch-search-guidance.md) | T003, T006, T011, T012, T016, T018 | optional train dependency and policy/value model |
| T010 | DONE | [Stochastic non-combat driver](T010-stochastic-non-combat-driver.md) | T002 | non-combat policy and native visible action/resource support |
| T011 | DONE | [Tactical feature contract v2](T011-tactical-feature-contract-v2.md) | T003 | feature, trainer-input, and model-input upgrades |
| T012 | DONE | [Structured battle resource outcomes](T012-structured-resource-outcomes.md) | T003, T004, T010, T016, T017 | persistent resource snapshots and outcome vectors |
| T013 | DONE | [Live CommunicationMod runtime adapter](T013-live-communicationmod-runtime-adapter.md) | T003, T011 | trained/search controller deployment in the real game |
| T014 | DONE | [Native public projection capability](T014-native-public-projection-capability.md) | T002, T003, T004, T010, T011 | native public projection and action parity |
| T015 | DONE | [Public run context and controlled history](T015-public-run-context-and-controlled-history.md) | T002, T003, T004, T011, T014 | sanitized context and ordered history |
| T016 | DONE | [Public-context artifacts, replay, and audit](T016-public-context-artifacts-replay-and-audit.md) | T003, T004, T005, T011, T014, T015 | migrations, replay, and coverage audit |
| T017 | DONE | [Stable sts_lightspeed source integration](T017-stable-lightspeed-source-integration.md) | T004, T010, T014, T016 | external source manifest and verifier |
| T018 | DONE | [Native terminal resource identity surface](T018-native-terminal-resource-identity.md) | T012, T017 | native terminal potion/deck/relic/key identities |
| T019 | DONE | [Codebase mechanical refactor](T019-codebase-mechanical-refactor.md) | T001--T018 except cancelled T007 | CLI decomposition and export cleanup |
| T020 | DONE | [sts_lightspeed fork maintenance line](T020-sts-lightspeed-fork-maintenance.md) | T017 | single active fork integration branch |
| T021 | DONE | [A20 battle-start coverage measurement](T021-a20-battle-start-coverage-measurement.md) | T004, T005, T008, T009, T010, T012, T016, T017, T018, T020 | A20 natural/constructed coverage and broad-training gate gaps |
| T022 | DONE | [A20 Oracle teacher dataset report](T022-a20-oracle-teacher-dataset-report.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021 | Oracle-like teacher dataset coverage and source linkage |
| T023 | DONE | [A20 Oracle teacher dataset scale-up](T023-a20-oracle-teacher-dataset-scale-up.md) | T004, T005, T006, T009, T012, T016, T017, T018, T020, T021, T022 | structured Oracle-like teacher scale-up and budget stability |
| T024 | DONE | [Oracle teacher search-guidance training bridge](T024-oracle-teacher-search-guidance-training-bridge.md) | T003, T004, T006, T009, T011, T012, T016, T017, T018, T020, T021, T022, T023 | teacher-targeted trainer input and diagnostic checkpoint |
| T025 | DONE | [Search telemetry baseline](T025-search-telemetry-baseline.md) | T005, T006, T009, T017, T020, T024 | shared search telemetry and baseline cost reporting |
| T026 | DONE | [Guidance checkpoint inference contract](T026-guidance-checkpoint-inference-contract.md) | T009, T011, T016, T018, T024 | checkpoint scorer contract for search guidance |
| T027 | DONE | [Teacher guidance calibration report](T027-teacher-guidance-calibration-report.md) | T026 | offline checkpoint-vs-teacher calibration |
| T028 | DONE | [Model-guided Oracle search controller](T028-model-guided-oracle-search-controller.md) | T025, T026, T027 | first versioned model-guided Oracle-like search controller |
| T029 | DONE | [Fixed-cohort model-guided search comparison](T029-fixed-cohort-model-guided-search-comparison.md) | T025, T028 | equal-source/equal-budget fixed-cohort comparison |
| T030 | DONE | [M1 model-guided search sandbox synthesis](T030-m1-model-guided-search-sandbox-synthesis.md) | T027, T029 | milestone synthesis and next task batch |
| T031 | DONE | [A20 coverage refresh and data gap report](T031-a20-coverage-refresh-data-gap-report.md) | T030 | post-M1 A20 coverage refresh before broader teacher/checkpoint work |
| T032 | DONE | [A20 narrow teacher and checkpoint diagnostic refresh](T032-a20-teacher-checkpoint-refresh.md) | T039 | narrow T039 source-contract teacher, trainer-input, checkpoint, and calibration diagnostic |
| T033 | DONE | [Public context model-input encoder contract](T033-public-context-encoder-contract.md) | T016, T030, T042 | structured public history, map/route, visible-Boss encoder boundary |
| T034 | BLOCKED | [Public-consistent hidden-future sampler boundary](T034-public-consistent-hidden-future-sampler.md) | T033, native sampler support | normal-information hidden-future sampling substrate |
| T035 | DONE | [Model-guided Oracle search v2](T035-model-guided-oracle-search-v2.md) | T032, T025, T028, T029 | deeper Oracle-like guidance after refreshed data/checkpoint evidence |
| T036 | DONE | [A20 search-controlled reachability probe](T036-a20-search-controlled-reachability-probe.md) | T006, T017, T020, T025, T029, T031 | search-controlled source reachability after T031 Act-1 gap |
| T037 | DONE | [A20 search-controlled reachability scale-up](T037-a20-search-controlled-reachability-scaleup.md) | T017, T020, T036 | scaled reproduction of historical Boss/Act2 reachability evidence |
| T038 | CANCELLED | [A20 source drift audit](T038-a20-source-drift-audit.md) | T037 under-reachability result | not needed because T037 recovered Boss/Act2 reachability |
| T039 | DONE | [Later-act/Boss source coverage contract](T039-later-act-boss-source-coverage-contract.md) | T037 accepted source decision | explicit artifact contract before T032 can consume source coverage |
| T040 | DONE | [Expert Non-Combat Driver v1](T040-expert-non-combat-driver-v1.md) | T010, T016, T017, T025, T036, T037, T039, T035 | A20 heuristic source-generation driver and coverage comparison |
| T041 | DONE | [Potion-enabled Oracle search repair](T041-potion-enabled-oracle-search-repair.md) | T006, T017, T020, T025, T036, T037, T039 | repair potion root mapping and no-potion/potion cohort comparison |
| T042 | DONE | [Assisted complete-run source generation](T042-assisted-complete-run-source-generation.md) | T040, T041 | assisted-run distribution, schedules, and coverage report |
| T043 | DONE | [Assisted teacher dataset and value/policy training](T043-assisted-teacher-value-policy-training.md) | T042, T033 | assisted teacher data and public student diagnostics |
| T044 | DONE | [De-assisted fixed-cohort evaluation](T044-de-assisted-fixed-cohort-evaluation.md) | T043 | low/no-assistance fixed-cohort model/search evaluation |
| T045 | DONE | [Post-T044 failure analysis and guidance path selection](T045-post-t044-failure-analysis.md) | T043, T044 | failure taxonomy after assisted model/search did not improve T044 outcomes |
| T046 | DONE | [Native root-prior allocation search surface](T046-native-root-prior-allocation.md) | T045, T017, T020 | native search surface for root playout allocation by explicit priors |
| T047 | DONE | [Root-prior guided search comparison](T047-root-prior-guided-search-comparison.md) | T046, T043, T044 | equal-source comparison of baseline, post-search guidance, and native root-prior allocation |
| T048 | DONE | [Root-prior guided search scale-up](T048-root-prior-guided-scale-up.md) | T047 | non-trivial matched-cohort scale-up of root-prior guided search evidence |
| T049 | DONE | [Root-prior complete-run reachability probe](T049-root-prior-complete-run-reachability-probe.md) | T048, T036, T037 | complete-run source reachability plumbing and bounded root-prior probe |
| T050 | DONE | [Root-prior reachability scale-up and shard merge](T050-root-prior-reachability-scaleup-and-shard-merge.md) | T049, T048, T036, T037 | sharded 50-run/arm complete-run reachability scale pass |
| T051 | DONE | [A20 search-controlled later-act source collection](T051-a20-search-controlled-later-act-source-collection.md) | T050, T049, T048, T036, T037 | broader matched source collection for Boss and later-act A20 starts |
| T052 | DONE | [T051 Boss/later-act fixed-cohort diagnostic](T052-t051-boss-later-act-fixed-cohort-diagnostic.md) | T051, T050, T048, T047, T005 | restored-battle diagnostic on T051 naturally reached Boss and later-act starts |
| T053 | DONE | [T052 root-prior allocation failure analysis](T053-t052-root-prior-allocation-failure-analysis.md) | T052, T047, T048, T051 | offline decision-level analysis of T052 root-prior regression and tied Boss starts |
| T054 | DONE | [Guardrailed root-prior allocation repair experiment](T054-guardrailed-root-prior-allocation-repair-experiment.md) | T053, T052, T048, T047, T046, T043 | versioned guardrailed root-prior repair experiment on the retained T052 fixed cohort |
| T055 | DONE | [Guardrailed root-prior fixed-cohort scale validation](T055-guardrailed-root-prior-fixed-cohort-scale-validation.md) | T054, T048, T047, T046, T044, T043 | repaired guardrail scale validation on the retained T048 fixed cohorts |
| T056 | DONE | [Post-T055 root-prior path selection](T056-post-t055-root-prior-path-selection.md) | T055, T054, T053, T052, T051, T050, T048 | guardrail-path closure and non-guardrail next-path selection |
| T057 | DONE | [Existing root-prior allocation telemetry diagnostic](T057-existing-root-prior-allocation-telemetry-diagnostic.md) | T056, T055, T053, T052, T048, T046, T043 | offline existing-root-prior allocation and selected-action telemetry diagnostic |
| T058 | DONE | [Root-prior selected-action telemetry replay diagnostic](T058-root-prior-selected-action-telemetry-replay-diagnostic.md) | T057, T052, T048, T046, T043 | instrumented or replayed selected-action identity comparison before any root-prior reachability or promotion branch |
| T059 | DONE | [Root-prior allocation repair experiment](T059-root-prior-allocation-repair-experiment.md) | T058, T052, T048, T046, T043 | bounded allocation repair experiment; closes the allocation-repair route after no T052/T053 improvement |
| T060 | CANCELLED | [Expert non-combat natural source coverage scale-up](T060-expert-non-combat-natural-source-coverage-scaleup.md) | T059, T040, T050, T039 | cancelled before execution; fixed-policy 10,000-run scale-up does not address the reachability-policy bottleneck |
| T061 | DONE | [A20 self-generated reachability bottleneck decomposition](T061-a20-self-generated-reachability-bottleneck-decomposition.md) | T059, T040, T050, T052 | battle-budget signal accepted; selects T062 as the single next task |
| T062 | DONE | [Battle Search v2 minimal surface](T062-battle-search-v2-minimal-surface.md) | T061, T052, T043, T046 | tree-internal policy prior and learned leaf value accepted; cost calibration exited early before outcome comparison |
| T063 | DRAFT | [Oracle-guided public battle learning](T063-oracle-guided-public-battle-learning.md) | T061, T062, T033 | simulator-only Oracle assistance with explicit public-policy transfer and no human trajectories |
| T064 | DONE | [Simulator-generated later-act curriculum](T064-simulator-generated-later-act-curriculum.md) | T033, T042, T043, T044, T052, T069, T070 | complete valid Case B: exposure-order curriculum did not improve the frozen transfer gates; recommends T065 to the planner |
| T065 | DONE | [Learned non-combat policy v1](T065-learned-non-combat-policy-v1.md) | T033, T040, T061, T064, T071, T074 | valid Case D diagnostic: frozen source selection found 107 replay-equivalent cross-split duplicates; no policy conclusion or downstream scientific stages |
| T066 | DRAFT | [Alternating joint policy improvement and natural scale gate](T066-alternating-joint-policy-improvement-and-natural-scale-gate.md) | T062, T063, T064, T065 | separate battle/non-combat policies with shared run value, followed by conditional natural scale-up |
| T067 | DONE | [Battle Search v2 inference-cost repair](T067-battle-search-v2-inference-cost-repair.md) | T062, T061, T052, T043 | exact-cache repair preserved semantics but had 0/866 hits; cost calibration remained infeasible and selected T068 |
| T068 | DONE | [Native-boundary batched inference feasibility](T068-native-boundary-batched-inference-feasibility.md) | T067, T062, T052, T043 | exact audit found only 207/261/398 synchronous singleton requests; batching closed and selected T069 |
| T069 | DONE | [Public-node feature-encoding projection feasibility](T069-public-node-feature-encoding-projection-feasibility.md) | T068, T067, T062, T052, T043 | exact projection preserved semantics, materially reduced cost, locked all calibration families, and recommended the original outcome comparison for planner consideration |
| T070 | DONE | [Battle Search v2 fixed-cohort outcome and budget-sufficiency audit](T070-battle-search-v2-fixed-cohort-outcome-and-budget-sufficiency-audit.md) | T069, T062, T052, T043 | fixed primary and high-budget audits complete; Case C recommends T064 to the planner without publishing a successor |
| T071 | DONE | [Post-T064 experiment execution simplification](T071-post-t064-experiment-execution-simplification.md) | T019, T064 | simplified T064 validation/reuse ownership and added lightweight detached long-job control before revising T065 |
| T072 | DONE | [Retire closed root-prior experiment executors](T072-retire-closed-root-prior-experiment-executors.md) | T053, T054, T055, T056, T057, T058, T059, T071 | retired the closed T053–T059 executor chain while preserving generic root-prior/search and T052 forward surfaces |
| T073 | DONE | [Forward surface health gate](T073-forward-surface-health-gate.md) | T019, T064, T067, T068, T069, T070, T071, T072 | PR #72 retired historical executor surfaces, restored neutral forward ownership, and requires a fresh post-merge repository quality review before T065 |
| T074 | DONE | [Core decision/policy boundary repair](T074-core-policy-boundary-repair.md) | T019, T073 | PR #73 repaired the forward runtime policy/batching/control boundary, moved non-combat and offline evaluation ownership, and contracted the simulator package barrel before any T065 publication decision |
| T075 | DONE | [Leakage-safe non-combat cohort repair](T075-leakage-safe-non-combat-cohort-repair.md) | T033, T040, T061, T064, T065, T071, T074 | PR #77 merged at c0cace6; global replay-group ownership passed exact selection, then the frozen target boundary produced a valid Case D diagnostic with no policy conclusion |
| T076 | DONE | [Checkpoint restore branch-isolation repair](T076-checkpoint-restore-branch-isolation-repair.md) | T075, T017, T020 | PR #79 merged at 3cd3f30; native checkpoint map aliasing was repaired and the retained state-67 regression passed without changing T075 science |
| T077 | DONE | [T075 same-experiment continuation](T077-t075-same-experiment-continuation.md) | T075, T076 | PR #81 merged at 3db86dd; exact T075 continuation reached the inherited TARGET Case D without downstream promotion |
| T078 | DONE | [Restored public-context fidelity repair](T078-restored-public-context-fidelity-repair.md) | T077, T076, T015, T016, T017, T020, T033 | PR #82 merged at d61be1d; state-160 restore fidelity repaired and the exact 320-state restore-only audit passed |
| T079 | DONE | [Battle Search state-utilization bounds recovery](T079-battle-search-state-utilization-diagnostic.md) | T078, T070, T069, T062, T052, T043, T017, T020 | PR #84 merged at dbee053; conservative exact-state bounds completed with an AMBIGUOUS terminal classification |
| T080 | DONE | [Battle value-target semantic alignment audit](T080-battle-value-target-semantics-audit.md) | T079, T070, T069, T062, T052, T043 | PR #86 merged at 1771203; exact frozen provenance audit completed with VALUE_TARGET_SEMANTICS_UNRESOLVED and no automatic successor |
| T081 | DONE | [Scientific artifact eligibility gate](T081-scientific-artifact-eligibility-gate.md) | T043, T044, T047, T048, T050, T051, T052, T062, T070 | PR #87 merged at 4a24f18; artifact integrity and scientific eligibility are now separate, fail-closed consumer gates with a durable historical claim-boundary audit |
| T082 | DONE | [T064 value-target semantic closure](T082-t064-value-target-semantic-closure.md) | T080, T081, T064, T043, T042 | PR #88 merged at 2acd1e8; qualified 460-row lineage audit confirmed VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED and permits one bounded value-target repair experiment |
| T083 | DONE | [Battle Search v2 leaf-value target contract audit](T083-battle-search-v2-leaf-value-target-contract.md) | T082, T081, T064, T062, T070 | PR #89 merged at c4f943e; accepted NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED and specifies a separate internal-leaf continuation-utility target-generation consideration without publishing a successor |
| T084 | DRAFT | [Search v2 internal-leaf continuation-utility target generation](T084-search-v2-internal-leaf-target-generation.md) | T083, T082, T081, T064, T062, T070 | Planner proposal for calibrated native-scale internal-leaf value targets; no training or outcome claim authorized |

Use the table, not per-task files or roadmap prose, when deciding whether a task
may receive a branch. Only `READY` rows should receive a new implementation
branch. `DRAFT` rows describe intended direction and must be reviewed against
latest `main` before publication. `BLOCKED` rows require their named external or
upstream capability. `CANCELLED` rows remain as historical planning records and
must not receive implementation branches.

Once a task is `READY`, its published acceptance criteria are the review
contract. A material scope change requires a documentation PR before an
implementation PR can be accepted.

## Current Planning Direction

The current planning contract is simulator-only self-generated policy
improvement with training-time Oracle assistance and separate battle/non-combat
decision modules. Human game trajectories, human action labels, and imitation of
human experts are outside the intended training path. See
[`../training_paradigm.md`](../training_paradigm.md).

T040's `expert_non_combat_v1` is retained only as a bootstrap exploration and
source-distribution policy. Its actions are not ground-truth labels and must not
be used as imitation targets for the final non-combat policy.

T060 was cancelled before execution because scaling the unchanged
`expert_non_combat_v1` plus 100-simulation battle profile from 1,000 to 10,000
runs would primarily estimate the same weak policy-induced occupancy
distribution more precisely. T061 replaced it with matched restored-battle and
complete-run interventions. Its accepted battle-budget signal selected T062 as
the single next task. T062 is complete through its published
calibration-infeasibility early exit: the tree-internal search surface is
accepted, no 93-record outcome comparison or controller promotion was
authorized, and T067 was selected for inference-cost repair and calibration
re-entry. T067 is complete: its exact public-node cache preserved semantics but
recorded 0 hits in 866 lookups, left `prior_only` and `value_only` infeasible at
minimum budget 1, ran no 93-record outcome comparison, and selected exactly
T068. T068 is complete: the existing native traversal exposed only synchronous
singleton requests in all three guided arms, so production batching,
calibration, the 93-record outcome comparison, and promotion remained
unauthorized. Its measured public-feature encoding cost selected T069. T069 is
complete: one exact search-scope public-context projection preserved accepted
scorer and search semantics, passed every material-improvement gate, and
locked all wall-clock and simulator-step calibration arms. T069 ran no
93-record outcome comparison. The planner reviewed that terminal evidence and
the accepted native tree-geometry capability, then proposed T070. T070 is
complete. Its frozen primary comparison did not pass the Search v2 promotion
boundary, while the bounded curve found the 100-simulation budget insufficient
but no high-budget guidance signal. The terminal Case C recommends T064 to the
planner without publishing it. T064 is complete with a valid negative Case B
and recommends T065. T071--T074 then completed the maintenance gate before that
publication decision: T071 simplified experiment execution/reuse, T072/T073
retired closed historical executor ownership, and T074 repaired the real
`controlled_run -> policy -> batching -> controlled_run` dependency cycle,
separated non-combat/offline evaluation ownership, and contracted the simulator
package barrel to 31 foundational exports.

The required post-T074 Planner quality review was completed before T065
implementation. The Main Maintainer approved the exact specification, and the
implementation preserved its legacy-CLI boundary and frozen source/selection
contract. T065 then completed Stage 0 and both 256-seed Stage 1 source arms, but
the exact selection gate found 107 replay-equivalent candidates crossing the
frozen seed-group split boundary. The independently audited result is a valid
Case D diagnostic: no policy conclusion, no candidate replacement, and no Stage
2--6 scientific execution. The retained report and source artifacts are recorded
on PR #74. T075 was the Planner-proposed architecture-recovery repair: it kept
those exact retained sources and unchanged replay identity, assigned global
replay-group ownership before the frozen quotas, and completed on PR #77. Its
exact 320-state selection passed; the frozen target validator then produced the
accepted A10/TARGET_INVALID Case D diagnostic at state 67. No target table,
training, gate, evaluation, policy conclusion, or promotion was produced. The
final retention manifest and all large outputs remain under the stable ignored
T075 artifact root recorded in the PR evidence.

T076 then repaired the native checkpoint boundary on PR #79. The root cause was
the shallow copy of `GameContext::map` (`shared_ptr<Map>`) inside
`StepSimulatorCheckpoint`; a later map branch could mutate the captured map and
change restored legal routes. The accepted native integration is pinned at
`cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083` on `stsrl/main`, and the exact
state-67 pre-repair failure and post-repair branch-isolation regression both
remain recorded in PR #79. T075's Case D result and retention are unchanged.
T077 is now complete after PR #81 merged at
`3db86dddb9685df00b197bf3d5a8e4bae4357c84`. Its final documentation head is
`bc23cb7b68c58c175818da820194137b588c91b2`, while the frozen scientific run
head is `b00e33ff8a150b3ad1b5b4c0cb8048d258ae621a`. It bound the accepted T076
integration `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083`, reused the exact T075
source/selection identities and 320-state cohort (selection SHA-256
`94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8`), and did
not recollect or reselect. The corrected TARGET used 16 spawned process
shards with observed effective concurrency; the earlier nominal 16-thread
attempt was abandoned and is non-authoritative. TARGET reached the inherited
Case D at state 160 (`restore public context mismatch`), independently
reproduced in a single-state debug. No replacement, TRAIN/GATE/EVAL, policy
conclusion, or promotion was produced. Retained T077 evidence remains under
`/mnt/d/DeadlycatCoding/STSRL/artifacts/t077-t075-same-experiment-continuation`:
reuse-boundary `4c70f3369ccc839e09482957cb8382cdbbdd05b6a45bc0b0469853e74bd46607`,
target outcome `e84eb0e4b5628771ea861c342a2e7540acb626797bf8c756f7c1c0172887218f`,
terminal `7ac65901f3bbbae586e4efdeb992afe03510de5bc7f74e0e0892b84ba5a3d4cf`,
and retention `c5fa6bfc467f8d2b624d8e0c3d8f488ed6b6e15d9f612d2e70eacb17383d387f`.
The focused T077 checks and final documentation checks passed; the full suite
at the frozen run head was `896 passed, 1 skipped, 2` known baseline or
environment failures. The durable worker-count rule is recorded once in
`docs/project_architecture.md`: reported simulator `worker_count` denotes
effective concurrent execution, not merely a configured thread count.

T078 is now complete after PR #82 merged at
`d61be1d70e404f8fbaa4de04e8a1643385051cce`. It repaired the canonical
`LightSpeedAdapter` checkpoint boundary after localizing the first state-160
public-context difference to the transition-only `completed_battle_outcome`
annotation; the native integration remained
`cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083`. State 160 passed immediate and
branch-then-restore checks, the accepted T076 state-67 regression remained
passing, and the exact retained 320-state restore-only audit passed with zero
mismatches, 16 effective processes, and no continuation or replacement. The
report is retained at
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t078-restored-public-context-fidelity-repair/restore-only-audit.json`
with SHA-256
`9abb6e76c7fe271884a37394b31058406ad0591b9949b7c109671d6d2ae539b1`. T075 and
T077 science and artifacts were not rerun, reclassified, or changed. The
T079 then completed the separate Battle Search state-utilization diagnostic
with an `AMBIGUOUS` terminal result; exact transposition remains parked under
its re-open conditions. T080 completed the value-target audit as
`VALUE_TARGET_SEMANTICS_UNRESOLVED` on the historical four-row smoke lineage.
T081 added the fail-closed Artifact Eligibility Contract, and T082 applied it to
the accepted non-smoke T064 lineage. T082 confirmed
`VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED`; T083 then accepted
`NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED` and fixed the required Search v2
leaf scalar to pinned-native continuation utility at the post-first-action
internal-leaf boundary. T084 is the current Planner `DRAFT`: it proposes only
calibrated internal-leaf target generation, with no training or outcome claim.
T063 and T066 remain `DRAFT` and are not implicitly promoted.

## Task Boundary And Artifact Rules

Each task must have explicit, reviewable inputs and outputs. A prerequisite may
provide a merged schema, command, fixture, or artifact-generation contract. It
does not provide an implicit local file dependency merely because one worktree
contains a checkpoint, JSONL file, report, or cohort.

Required artifacts must be reproducible by documented commands, committed as
small fixtures, or supplied through an explicit external/ignored artifact path
with schema, provenance, compatibility requirements, and identity checks. Large
generated artifacts remain outside Git. The durable contract is the schema,
manifest/provenance, command surface, hashes where applicable, and review
evidence.

GB-scale finalization must use bounded-memory paths when streaming or
summary-preserving aggregation can express the same result. Retained raw files
must live under a stable ignored path outside disposable review worktrees and
must have a lightweight retention manifest containing schema, provenance,
hashes, sizes, regeneration commands, compatibility requirements, retention
reason, possible downstream consumers, and deletion conditions.

A pull request submitted as ready for review must satisfy all published
acceptance criteria and required verification. Otherwise it remains draft and
names the missing criteria explicitly.
