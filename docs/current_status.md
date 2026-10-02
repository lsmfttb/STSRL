# Current Status

Last updated: 2026-10-02.

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

- The canonical native source identity, ref, and exact commit are owned by
  [`sts_lightspeed_source_manifest.json`](sts_lightspeed_source_manifest.json);
  T097 and T099 retain their historical lineage and evidence in their task
  contracts and PR records.
- T099 accepted the native particle/Search bridge capability. Its outer
  particle distribution is public-consistent; each continuation is
  `full_simulator_state_oracle_like`; returned values are a
  `full_state_continuation_strategy_fusion_proxy`. It does not perform
  cross-particle aggregation or action selection and does not claim an exact
  public Q value, exact posterior, or normal-information-optimal Search.
- T105 accepted the independently reviewed STSRL-007 native source at
  `refs/heads/stsrl/main @ 5afae22def0c69657b0139bfa21306aebac831af`.
  The additive, versioned stage trace reports safe control-flow status for six
  particle/Search bridge boundaries after a call or caught exception. It does
  not diagnose game-mechanics root cause or change the T099 bridge result and
  failure semantics. [Execution evidence](tasks/support/T105/maintainer-execution.md)
  records the lineage and clean-source verification.
- T107 accepted STSRL-008's additive
  `native-root-occurrence-mapping-diagnostic-v1` capability at
  `refs/heads/stsrl/main @ 1458522294d967e8985e1fd52cc15d7ebe7f2acd`.
  It provides fail-closed, non-secret root-occurrence mapping subreason
  observability. T105 remains the historical stage-observability provenance;
  T107 does not change T099 bridge semantics or diagnose/repair any T106 case.
  See the [T107 execution evidence](tasks/support/T107/maintainer-execution.md).
- T110 accepts STSRL-009's configuration-aware mapping at exact native pin
  `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`. Bridge/root/mapping/diagnostic
  v2 contracts explicitly retain no-potions public potion-use/discard actions
  as configuration-excluded, with null Search edges and values, not numeric
  zero. Historical v1 remains strict and independently recognizable. Exact
  lineage/tree proof, disposable rebuild, deterministic audit and Search
  invariance passed; [verification evidence](tasks/support/T110/implementation-verification.md)
  records the bounded capability result. T101 finite-value ranking/admission
  semantics are unchanged; scientific configured-domain support re-entry
  remains a separate contract, not an established cohort/convergence result.
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
a convergence result. The broader native public-consistent hidden-future
boundary remains unresolved. See [`tasks/ARCHIVE.md`](tasks/ARCHIVE.md) for
the exact lifecycle and terminal meaning of T034 and related tasks.

## Active scientific boundary

T101's frozen N=2 support-admission run ended as
`SUPPORTED_COHORT_INSUFFICIENT`: all 413 candidates were attempted across
A/B/C (93/192/128), with no admitted state. The first hash-ordered candidate
in each stratum was independently diagnosed as failing the native
T099 Search-v2 occurrence-mapping boundary; the cohort artifact retains the
generic bridge-failure exclusion for every attempt. No 24-state cohort,
canary, formal shard, or particle-stability result was produced. This is a
support-domain result, not convergence evidence. See
[`T101`](tasks/T101-bounded-particle-count-convergence.md) and its exact PR
record for detailed provenance. The terminal retention manifest is retained
under `artifacts/t101-bounded-particle-convergence-361a77d/admission/`
(`t101-terminal-retention-manifest-v1`, SHA-256
`922ef003d2fa15dea57f59c71fa99bfb6f5a418d48026b04ed3019d7e6cf4f97`).

T103 replayed that exact ordered population with the frozen N=2,
Search-v2@400, no-potion configuration. Its terminal is
`SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`, with zero admitted candidates:
70 have directly observed public-projection parity failure during bridge-report
checking (A/B/C 4/3/63), and 343 remain `OPAQUE_BRIDGE_FAILURE`
(A/B/C 89/189/65). The repaired pre-bridge context/action checks passed for all
413 candidates. The 70 returned reports establish that mapping and Search were
reached; those stages remain unknown for the 343 opaque exceptions. No valid
finite required root report was established. These are observable boundary
counts, not a fully localized root cause or convergence result; the earlier
three-candidate mapping diagnosis is not generalized. See the
[T103 execution record](tasks/support/T103/maintainer-execution.md) for exact
producer, retained hashes, resource cost and limitations.

T104 completed the same frozen census as `NATIVE_OBSERVABILITY_REQUIRED`, with
zero admissions and no changed T103 baseline class. All 70 projection failures
remain explicitly opaque: comparable pre-call/anchor/particle public payloads
and ordered actions agree, while the separately retained T014-to-T096 baseline
representation differences reproduce. Among 343 opaque bridge failures, 323
standalone sampler probes succeed and 20 fail. Neither outcome identifies a
monolithic bridge stage; all 343 require non-secret native stage observability
before a concrete monolithic repair boundary can be established. The terminal
uses that independent predicate, not the zero `NATIVE_STAGE_OPAQUE` class count.
See the [T104 execution record](tasks/support/T104/maintainer-execution.md) for
exact counts, hashes, producer/resource evidence and minimal observability needs.
No native change, mechanics repair or convergence execution was performed.

T105's accepted stage trace was used by the bounded T104 diagnostic re-entry
completed in T106; T105 did not authorize a mechanics repair or convergence.
T063 and T066 remain non-active scientific directions; see
[`tasks/ARCHIVE.md`](tasks/ARCHIVE.md) for their exact lifecycle and terminal
meanings. No task is promoted merely by appearing in a document or Planner Issue.

T106 completed the exact 343-row T104 Part-B re-entry under the frozen
replicate-0, N=2, unguided Search-v2@400, no-potions configuration and the
T105-accepted native stage-observability pin. All 343 prior bridge failures
reproduced with valid structured traces: 323 first failed at root-occurrence
mapping and 20 at public-fidelity validation. These are bounded first failed
control-flow stages, not mechanics root causes or repair efficacy. T106 did not
replay Part A, change native source, run N>2 convergence, train or promote a
controller. See the [T106 execution record](tasks/support/T106/maintainer-execution.md)
and [task archive](tasks/ARCHIVE.md) for exact provenance and retained evidence.

Post-T106 Planner review, including an external architecture audit of
`SnyderConsulting/sts_ml`, does not change the accepted T106 census. The external
solver remains architecture evidence only, not accepted STSRL correctness,
particle-convergence, or public-fidelity evidence. T107 accepted STSRL-008's
exact-source root-occurrence mapping subreason observability capability as
`NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED`; this is a
source/capability result, not a replay or mechanics diagnosis. T108 has now
completed the exact 323-row T106 root-mapping re-entry under the frozen
replicate-0, N=2, unguided Search-v2@400, no-potions configuration. All 323
reproduced the accepted root-mapping-stage baseline and classified from valid
structured native diagnostics as
`missing_non_card_direct_search_root_match` (A/B/C 84/174/65); the other six
accepted failure subreasons had count zero. This is a bounded native
mapping-control-flow census, not a mechanics root-cause or repair result. The
separate 20 public-fidelity-stage failures remain unresolved and reserved for
their own diagnosis lane. No mapping repair, Part-A replay, N>2 convergence,
training, controller promotion, T034 closure, or T063/T066 activation is
authorized by T108.

T109's read-only static audit establishes a configured action-domain mismatch
for those exact 323 accepted T108 failures: all 322 retained `potion` and one
`potion_discard` public-action occurrences have zero direct Search-root matches
under frozen `include_potions=false`, while the mapper requires a direct match
for every non-card public occurrence. T108 did not retain per-row input-state
metadata; the exact native producer emits these potion action kinds only from
its `PLAYER_NORMAL` public-action branch. This is not a game-mechanics defect,
repair, or repair-efficacy result. No dynamic witness ran, and the repair
architecture remains open. The separate 20 public-fidelity failures remain
outside T109. See the [T109 static-analysis record](tasks/support/T109/static-analysis-record.md).

T111 re-entered N=2 admission under the T110 configuration-aware bridge for the
exact T101-ordered 413-candidate source population (A/B/C 93/192/128), with
replicate 0, `particle_start=0`, unguided Search-v2@400, and
`include_potions=false`. All three strata exhausted with 0/8 admissions. The
retained structured exclusions are 385 strict T110-v2 bridge
schema/classification failures (A/B/C 87/175/123), 8 searched-value
unavailable/non-finite/unvisited cases (1/2/5), and 20 accepted structured
bridge failures (5/15/0). Configuration-excluded public potion actions remain
legality/parity evidence and were not assigned Search values or ranked; no
admitted cohort or convergence result was produced. The terminal is
`CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT`. No N>2 run, convergence,
larger replay, native change, training, or promotion occurred. Planner selected
a static-first audit of the dominant 385 validator-boundary exclusions as the
next diagnostic direction; that direction does not authorize a replay. See the
[T111 PR evidence](https://github.com/lsmfttb/STSRL/pull/129#issuecomment-5943751115)
and [task archive](tasks/ARCHIVE.md) for the terminal record and retention
manifest identity.

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
- T080--T084 repaired and audited value-target semantics and produced qualified
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
