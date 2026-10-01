# T109: Static-First Root-Mapping Action-Domain Audit

Artifact Eligibility Required: true

## Objective

Determine whether T108's exact 323 `missing_non_card_direct_search_root_match` failures are explained by a contract mismatch between the public legal-action domain and the Search-v2 root-action domain under the frozen `include_potions=false` configuration.

T109 is deliberately **static-first**. It must exhaust production-code structure, accepted retained data, configuration semantics, and Slay the Spire action semantics before any new simulator execution, telemetry addition, native change, or population replay is considered.

This task also publishes the repository-wide diagnostic-method rule in `docs/diagnostic_method.md` and wires that rule into `docs/tasks/TEMPLATE.md`. The rule is part of the T109 contract, not advisory prose.

## Current Main Baseline

Publication base:

`main @ 6ba76017463c9f7cc11686a2c655f78203ce799a`

Accepted predecessor terminals:

- T106: `PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED`;
- T107: `NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED`;
- T108: `ROOT_OCCURRENCE_MAPPING_SUBREASON_CENSUS_ESTABLISHED`.

T108 established on the exact 323 accepted T106 root-mapping identities, A/B/C `84/174/65`, that all 323 reproduced the root-occurrence-mapping failure and all 323 classified from valid structured native diagnostics as:

`missing_non_card_direct_search_root_match`

The other six accepted failure subreasons had count zero. T108 did not establish a mechanics root cause or authorize repair.

The accepted native source remains:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1458522294d967e8985e1fd52cc15d7ebe7f2acd`

The relevant accepted native code currently has two independently generated action surfaces:

1. `enumerateBattleActions(const BattleContext&)`, used by root-occurrence mapping to enumerate public legal battle actions; and
2. `BattleScumSearcher2::enumerateActionsForNode(...)`, used by Search-v2 to materialize node/root edges.

For `InputState::PLAYER_NORMAL`, the first enumerator includes valid End Turn, card, potion-use, and potion-discard actions. Search-v2 enumerates cards, includes potion actions only when `includePotions` is true, and adds End Turn. T108's frozen Search setting was `include_potions=false`.

This code-level observation is a candidate mechanism, not yet the T109 terminal. T109 must verify it against the accepted T108 retained structured metadata and all relevant action/input-state branches before drawing a conclusion.

## Dependencies

- T081 artifact eligibility rules;
- T099 particle/Search bridge semantics;
- T106 exact 323 root-mapping subset provenance;
- T107 accepted safe root-mapping diagnostic fields;
- T108 exact retained 323-row diagnostic census;
- `docs/diagnostic_method.md` introduced on this PR.

## Inputs And Artifacts

Primary accepted T108 retained root:

`artifacts/t108-root-occurrence-mapping-subreason-diagnostic-41a789a/full-323-attempt-2/`

Accepted T108 artifacts:

- candidate rows, schema `t108-root-mapping-subreason-rows-v1`, SHA-256 `bbd8db3dafcfcb729f198b1f5c7c86d6d1156ef0041ed74e8d00965e0a1f8c26`;
- aggregate report, schema `t108-root-mapping-subreason-report-v1`, SHA-256 `df61a122d7d01d9aa89fccfefe578c09e0c304a2841887146aedf67af5c2bbd6`;
- execution record, schema `t108-execution-record-v1`, SHA-256 `8faf47cf79807bde3ef70182ad798ecb27a6d670cf2ae8dc70a2fbce1b7a64fb`;
- retention manifest, schema `t108-root-mapping-subreason-retention-manifest-v1`, SHA-256 `35f8e53f75f98134922a7725d25986696678f102ff1808000c2e81fc934fa8e2`.

T109 must use these artifacts read-only. Existing T108 fields such as `public_action_kind`, `direct_match_multiplicity`, `mapping_subreason`, input-state/stage metadata already accepted by T107/T108 may be summarized. T109 must not recover or expose raw action bits, private Search nodes, hidden simulator state, hidden RNG state, exception prose, or other information outside the accepted safe surface.

Required T109 durable outputs are a compact static-analysis/evidence record under `docs/tasks/support/T109/` and the final task lifecycle/current-state updates prepared before landing. Large generated artifacts are not expected.

## Artifact Eligibility Contract

Reuse mode: `scientific_quality_claim` limited to causal diagnosis of the already accepted T108 failure boundary.

Required predicates:

- all four T108 artifact identities and hashes match the accepted T108 record;
- the analyzed row population is exactly the accepted 323-row T108 terminal population;
- structured metadata coverage and any missing values are counted explicitly;
- production native code is inspected at exact accepted pin `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- no conclusion is derived from exception text or private payloads;
- no dynamic witness is used unless the Static Sufficiency Gate below explicitly leaves a material ambiguity.

If a required T108 artifact, hash, safe field, or exact native source cannot be verified, fail closed to `STATIC_DIAGNOSIS_INPUT_INCOMPLETE`. Do not compensate with a fresh full replay.

## Scope

T109 owns four things:

1. a static action-domain/data-flow audit of the T108 root-mapping boundary;
2. a read-only audit of already retained T108 safe diagnostic metadata;
3. at most a minimal deterministic witness if and only if static evidence cannot distinguish the remaining mechanisms; and
4. the durable repository-wide static-first diagnostic-method rule.

The central question is whether the current contracts are effectively:

- public mapping domain = full valid public battle-action domain; while
- Search root domain = configured Search action domain; and
- the mapper nevertheless requires every public occurrence to have a Search root match.

T109 must analyze this question separately for all action kinds/input states relevant to the 323 retained failures rather than assuming in advance that the unmatched action is a potion.

## Static Analysis Gate

Before any simulator invocation, T109 must produce a source-grounded action-domain matrix covering at minimum:

- `PLAYER_NORMAL` card actions;
- `PLAYER_NORMAL` potion use;
- `PLAYER_NORMAL` potion discard;
- `PLAYER_NORMAL` End Turn;
- `CARD_SELECT` action forms if any retained T108 row can reach that input state;
- the effect of `includePotions=false` on Search enumeration;
- the matching rule used by `validateSearchRootMapping` for direct non-card actions;
- whether any other filter, validity check, canonicalization, or state transition can explain a missing non-card direct match.

For each row/action class, state:

- producer of the public action;
- producer of the Search root edge;
- relevant configuration/filter;
- mapping expectation;
- predicted T107/T108 diagnostic branch if the edge is absent;
- whether the prediction is deductive from production code or only a hypothesis.

The audit must explicitly inspect, at the accepted native pin, at least:

- `enumerateBattleActions`;
- `BattleScumSearcher2::enumerateActionsForNode`;
- card/potion/card-select enumeration helpers they call where material;
- `validateSearchRootMapping`;
- action type/bit construction needed to distinguish domain exclusion from representation mismatch.

## Retained-Data Gate

Still without simulator execution, T109 must inspect the accepted T108 rows/report and report:

- exact count of classified rows with safe `public_action_kind` available;
- cross-tab of `public_action_kind` over the exact 323 rows;
- cross-tab of `direct_match_multiplicity` over those rows;
- any relevant safe input-state/action-class metadata already retained;
- whether every row's observed structured metadata matches the static mechanism prediction;
- any counterexample identity/class, if present.

A summary based only on the T108 terminal label `missing_non_card_direct_search_root_match` is insufficient; use the already retained safe fields that discriminate the action-domain mechanism.

## Static Sufficiency Gate

T109 must stop before dynamic execution if production code plus accepted retained safe data establish one mechanism without a remaining material alternative.

In particular, `ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED` is permitted without any new simulator execution only if all of the following are established:

1. the affected T108 rows have complete enough safe action-kind metadata to identify the unmatched non-card class(es);
2. those class(es) are enumerated into the mapping/public legal domain under the frozen state semantics;
3. those same class(es) are excluded from Search root enumeration by the frozen Search configuration or another directly demonstrated configured domain restriction;
4. `validateSearchRootMapping` nevertheless requires a direct root match for them and emits the observed T108 subreason when none exists;
5. there is no retained counterexample requiring an additional mechanism; and
6. no representation/identity hypothesis is needed to explain the observed rows once the domain exclusion is accounted for.

If these conditions are satisfied, do **not** run a witness merely for reassurance. The task should record the static causal chain, bounded claim, architectural repair choices that remain open, and stop.

If the evidence instead shows a non-card kind that Search should include under the frozen configuration, or the retained safe metadata is insufficient to distinguish domain exclusion from representation mismatch, T109 must record the exact unresolved fact before any dynamic work is considered.

## Minimal Witness Gate

Dynamic execution is not part of the default T109 path.

A dynamic witness may be authorized only after Maintainer verifies a static-analysis record showing a specific unresolved material fact that cannot be answered from existing production code and accepted T108 artifacts.

If authorized, the witness must be the smallest deterministic test that distinguishes the remaining mechanisms:

- select at most one accepted T108 identity per unresolved observed action kind, maximum three identities total;
- select deterministically by earliest accepted T108 order within each unresolved kind;
- no random resampling and no population prevalence estimate;
- no new telemetry/native patch unless the witness is impossible with existing accepted interfaces;
- no full 323 replay;
- no 20-row public-fidelity replay;
- no 70-row Part-A replay;
- no N>2 run;
- no training/promotion run.

A configuration contrast such as `include_potions=false` versus `true` may be used only as a diagnostic intervention on the minimal witness, never as replacement scientific evidence for T108 and never as a controller/search promotion experiment.

If even the minimal witness requires a new observability surface, T109 terminates `STATIC_DIAGNOSIS_REQUIRES_NEW_OBSERVABILITY` with the exact unavailable fact. A separate Planner task is required before any native observability change.

## Diagnostic Method Amendment

This PR introduces `docs/diagnostic_method.md` as the repository-wide method for debugging, root-cause, failure-localization, and observability tasks. `docs/tasks/TEMPLATE.md` is amended so future diagnostic task contracts must either satisfy that method or explicitly state why it does not apply.

The durable rule is:

> use static production-code/data-flow/configuration/game-semantic analysis first; use existing retained evidence second; use the smallest discriminating dynamic witness third; add observability or scale to a census only when the exact unresolved fact and the reason smaller evidence cannot answer it are written down.

After every new observation layer, return to source/data-flow analysis before authorizing another observation layer.

## Out Of Scope

T109 does not authorize:

- a native mapping repair;
- an STSRL mapping repair;
- changing `include_potions` policy;
- deciding yet whether the correct architecture is to filter the public domain, retain non-searched root identities, or change the mapping invariant;
- replay of all 323 rows;
- diagnosis of the separate 20 public-fidelity failures;
- T104 Part-A replay;
- new native telemetry by default;
- N>2 convergence;
- particle aggregation redesign;
- training, evaluation, controller promotion, complete-run claims, or T034 closure.

## Design Constraints

- Exact-head and artifact-provenance discipline remains unchanged.
- Static claims must cite concrete production functions/branches and configuration semantics, not paraphrased expectations.
- Existing accepted retained telemetry must be reused before generating new telemetry.
- A prevalence question and a causal-mechanism question are distinct. Do not run a census to answer a mechanism already established deductively.
- A diagnostic intervention that changes configuration is not evidence that the changed configuration should be promoted.
- If the static explanation is established only for a subset of observed action kinds, do not generalize it to the rest.
- Do not treat the game's full legal action set and Search's configured action set as identical unless code establishes that identity.

## Deliverables

- `docs/tasks/T109-static-first-root-mapping-action-domain-audit.md`;
- `docs/diagnostic_method.md`;
- amended `docs/tasks/TEMPLATE.md` referencing the diagnostic method;
- a retained compact T109 evidence record containing the static action-domain matrix, T108 safe-field cross-tabs, exact source references/pin, conclusion, counterexamples, and whether dynamic execution occurred;
- focused tests/documentation checks needed to keep the new diagnostic-method reference and T109 contract discoverable;
- final `ARCHIVE.md` and `current_status.md` updates before landing.

No simulator executor is required if the Static Sufficiency Gate passes.

## Acceptance Criteria

T109 passes only if:

1. exact T108 retained artifacts and exact native source are qualified;
2. the production public-action, Search-action, and mapping data flows are analyzed together under the actual frozen configuration;
3. retained T108 safe metadata is used to test the static mechanism across the exact 323 accepted rows;
4. no new dynamic execution occurs when static evidence is sufficient;
5. if dynamic evidence is necessary, it obeys the Minimal Witness Gate exactly;
6. the final terminal does not overclaim a mechanics defect, repair efficacy, Search improvement, or particle convergence;
7. `docs/diagnostic_method.md` and the template amendment land with the task.

Allowed scientific terminal classifications are:

- `ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED`;
- `STATIC_DIAGNOSIS_INPUT_INCOMPLETE`;
- `STATIC_DIAGNOSIS_INCONCLUSIVE`;
- `STATIC_DIAGNOSIS_REQUIRES_NEW_OBSERVABILITY`;
- `MINIMAL_WITNESS_CONTRADICTS_STATIC_HYPOTHESIS`.

Any terminal other than the first must state the exact unresolved or contradictory fact and must not silently trigger a larger experiment.

## Required Verification

Before any dynamic execution:

- verify T108 artifact schemas, hashes, population count/order, and retained safe-field coverage;
- verify native source pin exactly;
- inspect the named production source paths/functions at that pin;
- run repository documentation/task-contract tests applicable to the new files;
- run `git diff --check`.

If the Static Sufficiency Gate passes, these plus independent Maintainer review are the complete scientific execution path; do not manufacture a simulator run requirement.

If a minimal witness is authorized, its exact identities, reason, configuration, commands, resource bounds, and expected distinguishing outcomes must be recorded before execution.

## Legacy Reference

T108's full 323-row replay is historical evidence and must not be rerun merely to support T109. T106/T107/T108 source and evidence may be consulted read-only. No selective port of a historical diagnostic executor is required unless a minimal witness is independently justified.

## PR Report

The PR report must state:

- publication base and exact approved spec head;
- exact T108 artifacts consumed;
- exact native source pin inspected;
- static action-domain matrix conclusion;
- T108 safe `public_action_kind` and direct-match cross-tabs;
- whether the Static Sufficiency Gate passed;
- whether any dynamic witness ran, and if so why static evidence was insufficient;
- terminal classification and bounded interpretation;
- confirmation that no unauthorized replay, telemetry expansion, repair, convergence, training, or promotion occurred.
