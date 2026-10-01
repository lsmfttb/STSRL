# T110: Native Configuration-Aware Root-Mapping Source Acceptance

Artifact Eligibility Required: false

## Objective

Accept the independently reviewed and merged `sts_lightspeed` STSRL-009 configuration-aware root-occurrence mapping capability into STSRL as one exact, reproducible native source dependency.

T110 is an **integration/provenance and versioned-contract acceptance task**. It is not a scientific support replay, not a convergence experiment, not a public-fidelity diagnosis, and not a redesign of Search policy.

The native result to accept is:

- repository: `https://github.com/lsmfttb/sts_lightspeed.git`;
- active branch/ref: `stsrl/main` / `refs/heads/stsrl/main`;
- previous accepted STSRL manifest pin: `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- native issue: `lsmfttb/sts_lightspeed#25` (`STSRL-009`);
- reviewed native PR: `lsmfttb/sts_lightspeed#26`;
- exact independently reviewed PR head: `d26f557bf33639f921e5cf16c220d0e1e357f6f2`;
- durable independent exact-head PASS comment: `5931892904`;
- merged native result: `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`.

The sole T110 question is:

> can STSRL prove that exact merged native result is on the accepted `stsrl/main` lineage, pin and rebuild it reproducibly, and strictly accept the new v2 configuration-aware mapping/report contract without weakening fail-closed behavior, converting missing values to numeric zero, or silently changing the historical v1 contract?

A successful T110 accepts only the native capability and STSRL-side contract/verifier support required for a later bounded support re-entry.

## Publication Baseline

Publication base:

`main @ f59fcbe78a0d49dfedc54386bc618d13a6f0e7b5`

Current STSRL source manifest pin:

`1458522294d967e8985e1fd52cc15d7ebe7f2acd`

Target pin:

`6496fc1c7e629a374b72bd94f7fd29afe29c7f62`

Active integration ref remains:

`refs/heads/stsrl/main`

At publication time Planner independently verified from GitHub state that:

- native merge `6496fc1c7e629a374b72bd94f7fd29afe29c7f62` has parents exactly:
  - `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
  - `d26f557bf33639f921e5cf16c220d0e1e357f6f2`;
- reviewed head and merge result point to the same source tree `3e5e3d2c73e70bce2a726a563208c1fbb66c5c0c`, so the merge introduces no file-level delta beyond the reviewed head;
- native `refs/heads/stsrl/main` resolves exactly to `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`.

Final acceptance must reproduce these facts independently rather than treating publication-time verification as final evidence.

## Dependencies

- T017: exact external source manifest and canonical disposable-source verifier;
- T020: single active `sts_lightspeed` integration-line governance;
- T099: accepted STSRL-006 particle/Search bridge and historical v1 bridge validator;
- T105: accepted particle-search stage observability;
- T107: accepted root-occurrence mapping diagnostic v1 contract;
- T109: `ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED`, establishing the configured public/Search action-domain mismatch under `include_potions=false`;
- native issue `lsmfttb/sts_lightspeed#25`;
- native PR `lsmfttb/sts_lightspeed#26`, independently accepted at exact head `d26f557bf33639f921e5cf16c220d0e1e357f6f2` and merged as `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`.

## Diagnostic Method Gate

Not applicable as a new diagnosis task. T109 already established the action-domain mismatch and STSRL-009 is the separately reviewed repair. T110 verifies source identity and the repaired interface contract; it must not reopen causal diagnosis by adding telemetry or replaying a population.

## Scope

### 1. Exact native source pin

Update `docs/sts_lightspeed_source_manifest.json` so the integration repository/branch/ref remain unchanged and the exact integration commit becomes:

`6496fc1c7e629a374b72bd94f7fd29afe29c7f62`.

The exact commit, not the moving ref, remains the reproducibility authority.

### 2. Source lineage and reviewed-tree proof

Final evidence must prove from the actual Git graph that:

- previous accepted pin `1458522294d967e8985e1fd52cc15d7ebe7f2acd` is an ancestor/first merge parent of the target result;
- reviewed implementation head `d26f557bf33639f921e5cf16c220d0e1e357f6f2` is contained in the target result;
- reviewed head and merged result have no file-level semantic delta, preferably by exact tree identity and/or a quiet diff;
- active native `refs/heads/stsrl/main` resolves exactly to `6496fc1c7e629a374b72bd94f7fd29afe29c7f62` at acceptance time.

### 3. Canonical disposable-source verification

`scripts/verify_lightspeed_source.sh` remains the canonical verifier and must build/import the exact manifest-selected source from a fresh detached/disposable checkout.

The verifier must be updated from its T107 pin/schema assumptions to T110 and must fail closed on any other integration commit or moving-ref mismatch.

It must not pass because of stale native build directories, inherited `PYTHONPATH`, copied binaries, implementation worktrees, or local source edits.

### 4. Strict versioned bridge validation

The current STSRL T099 validator is a strict historical v1 validator: it expects every public legal occurrence to own a Search edge and rejects `unsearched_legal_action_count != 0`. The new native source intentionally returns a v2 successor contract, so T110 must adapt STSRL validation explicitly rather than weakening v1 semantics.

Implementation may use a strict version dispatcher, a dedicated v2 validator, or an equivalent design, but all of the following are required:

- historical `native-battle-public-particle-search-v1` remains independently recognizable and is not silently reinterpreted;
- current accepted native source must be verified specifically as `native-battle-public-particle-search-v2` / `StepSimulator.sample_hidden_future_particles_search.v2`;
- unknown schemas fail closed;
- canonical T110 verification cannot succeed by falling back to v1 expectations.

For v2, require at minimum:

- bridge schema `native-battle-public-particle-search-v2`;
- root schema `native-battle-search-root-v2`;
- occurrence mapping schema `native-search-root-occurrence-equivalence-v2`;
- mapping diagnostic schema `native-root-occurrence-mapping-diagnostic-v2`;
- `root_action_mapping_completion_semantics == "every_public_occurrence_classified_and_every_search_edge_covered"`;
- `semantic_boundary.configuration_excluded_action_values == "not_evaluated_not_numeric"`.

### 5. Configuration-excluded row semantics

Every public action occurrence must retain public identity and order and have exactly one accepted mapping classification:

- `searched_direct`;
- `searched_mechanical_duplicate_card_occurrence`;
- `search_configuration_excluded`.

For a `search_configuration_excluded` row, STSRL validation must require all of the following together:

- public action kind is `potion` or `potion_discard`;
- bridge/root `include_potions` is exactly `false`;
- `configuration_exclusion_reason == "include_potions_false"`;
- `search_tree_present == false`;
- `search_edge_index == null`;
- `search_equivalence_source_edge_index == null`;
- `search_equivalence_mapping_mode == null`;
- mapping-row `search_edge_index == null`;
- mapping-row `mapping_mode == null`;
- mapping-row `source_action == null`;
- mapping-row `edge_public_occurrence_count == null`;
- `visits == 0`;
- `evaluation_sum == null`;
- `mean_value == null`.

`visits=0` is a work/count fact only. It must never be used to synthesize numeric zero for an absent Search evaluation or mean value.

No generic `edge == null => configuration excluded` rule is permitted.

### 6. Searched-row and edge-coverage semantics remain strict

For searched rows, preserve the accepted T099 semantics:

- one concrete non-negative Search edge index;
- direct mapping mode or existing adjacent mechanically-equivalent duplicate-card mode;
- source action identity present;
- no raw action bits in the sanitized public contract;
- Search values/work fields retain their existing semantics.

Require global consistency:

- every public occurrence is classified;
- `searched + configuration_excluded == classified == public legal occurrence count`;
- searched/mapped count equals the number of public occurrences with concrete Search edges;
- `unsearched_legal_action_count == configuration_excluded_public_action_count`;
- `unmapped_search_edge_count == 0`;
- every actual Search root edge remains covered by one or more public occurrences.

End Turn, card-select actions, potion actions under `include_potions=true`, or any other missing required edge must not be accepted as configuration-excluded.

### 7. Mapping diagnostic v2 compatibility

The existing T107 diagnostic validator must be extended/versioned without silently redefining v1.

For diagnostic v2, preserve the accepted failure vocabulary and validate the added counts:

- `public_occurrences_classified`;
- `searched_public_occurrence_count`;
- `configuration_excluded_public_occurrence_count`.

On successful v2 mapping:

- diagnostic status is `completed`;
- subreason is `mapping_completed`;
- every public occurrence is classified;
- searched + configuration-excluded equals classified;
- `public_occurrences_mapped == searched_public_occurrence_count`;
- every Search edge is covered.

The seven existing fail-closed subreasons remain authoritative and must not be collapsed into a generic success class.

### 8. Accept the deterministic STSRL-009 native audit

Require `StepSimulator.stsr009_configuration_aware_root_mapping_audit` with schema:

`native-stsr009-configuration-aware-root-mapping-audit-v1`

and require every reviewed predicate to be true:

- `potion_use_excluded`;
- `potion_discard_excluded`;
- `public_action_order_preserved`;
- `searched_actions_preserved`;
- `no_fake_values`;
- `mapping_schema_versioned`;
- `diagnostic_v2_counts_correct`;
- `required_missing_non_card_fails_closed`;
- `enabled_potion_missing_discard_fails_closed`;
- `uncovered_edge_fails_closed`;
- `search_surface_and_work_unchanged`;
- `all_search_edges_covered`.

The audit is capability evidence, not a scientific population result.

### 9. Preserve Search/sampler/fidelity behavior

T110 must verify that the accepted source does not change the no-potions Search policy or manufacture searched potion edges.

Preserved behavior includes:

- `include_potions=false` Search root domain remains card/End-Turn driven as before;
- duplicate-card mechanical equivalence remains unchanged;
- Search edge surface, visits, evaluations, work counters, and RNG state are not changed by mapping/report construction;
- T096 public projection and hidden-future sampler semantics remain unchanged;
- public-fidelity validation remains unchanged;
- STSRL-007 stage ordering remains Search setup/execution before root occurrence mapping;
- no fallback, retry, alternate Search, or reseed path is introduced.

### 10. Information-safety and test-injection boundary

The accepted v2 surfaces must not expose raw action bits, `specialData`, hidden `BattleContext`, hidden draw order, private intent, native RNG state/output, private Search nodes/continuations, hidden trajectories, or exception prose as scientific data.

Production callers must not be able to select internal mapping failure injection. Fixed test-only audit injection may remain private to native deterministic audit functions.

### 11. Capability inventory

Update `docs/sts_lightspeed_source_manifest.json` capability inventory so the new accepted STSRL-009 capability is explicit and machine-discoverable.

Prefer a new capability record such as `native_stsr009_configuration_aware_root_mapping` with T110 provenance. If the historical T099/T107 capability descriptions must be amended to avoid a false current-runtime statement, make only the minimum version-aware clarification and retain their historical provenance and v1 meaning.

Do not erase T099/T107 from the capability inventory.

### 12. Scientific downstream boundary

T110 must **not** silently amend T101's scientific finite-value/ranking contract.

Current T101 code requires finite Search values for every public root row. Under the accepted v2 contract, configuration-excluded potion rows intentionally have no Search value. Deciding how T101 admission/convergence should treat that distinction is a separate scientific contract question.

Therefore T110 may make generic/native bridge validation v2-aware, but it must not:

- convert excluded rows to numeric zero;
- drop excluded public actions from the public legal-action identity surface;
- redefine T101 ranking statistics;
- declare T101 N=2 support restored;
- execute N=2/4/8/16/32 convergence.

A later Planner task must explicitly define the configured-Search-domain scientific comparison/admission semantics before convergence resumes.

## Artifact Eligibility Contract

None.

T110 consumes source identity, Git lineage, versioned native capability metadata, and bounded verifier/test evidence only. It produces no scientific corpus and makes no population-quality claim.

## Required Verification

At minimum, implementation/final evidence must report and pass:

1. manifest parser/tests for exact pin `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`;
2. exact Git lineage proof for previous pin, reviewed head, merge result, and active ref;
3. exact reviewed-tree equivalence proof between `d26f557bf33639f921e5cf16c220d0e1e357f6f2` and merge result;
4. canonical disposable-worktree verification through `scripts/verify_lightspeed_source.sh` against the exact pinned commit;
5. native API smoke against that verifier-built module;
6. existing T096 visibility/sampler regressions against that exact source;
7. existing STSRL-006 bridge deterministic audit against that exact source;
8. existing STSRL-007 stage-observability regression/audit;
9. existing STSRL-008 mapping-subreason audit under diagnostic v2 compatibility;
10. STSRL-009 configuration-aware root-mapping audit with all twelve predicates true;
11. strict v2 validator tests for searched direct, searched duplicate-card, potion use exclusion, potion discard exclusion, public order, null/no-value semantics, and aggregate counts;
12. negative tests proving arbitrary null/missing End Turn, enabled-potion missing discard, uncovered Search edge, unknown classification/reason, inconsistent counts, and numeric-zero substitution fail closed;
13. regression tests proving historical v1 schema is either still strictly validated by its historical path or is explicitly retained as a separate recognized historical contract rather than reinterpreted;
14. proof that production bridge callers cannot select failure injection;
15. proof no new hidden/private data appears in accepted surfaces;
16. Search-v2 geometry/state-utilization compatibility checks sufficient to ensure mapping/report acceptance did not replace Search semantics;
17. repository quality gates applicable to touched Python/tests/docs plus `git diff --check`.

The canonical verifier must exercise the exact native binary it built from the pinned disposable checkout. No T106/T108 population replay is authorized.

## Acceptance Criteria

T110 passes only if all of the following are true:

- manifest pins exactly `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`;
- active integration ref remains `refs/heads/stsrl/main` and resolves exactly to the pin;
- old accepted pin and reviewed head are both proved in the target lineage;
- merged result is source-tree equivalent to the independently reviewed head;
- canonical verifier builds/imports only the exact pinned source from a disposable checkout;
- bridge/root/mapping/diagnostic v2 schemas are explicitly validated;
- public potion use/discard rows under `include_potions=false` are retained in public order as configuration-excluded rows with null edge/source/value semantics and zero visits only;
- no missing evaluation is converted to numeric zero;
- searched direct and duplicate-card rows preserve their existing mapping semantics;
- End Turn, enabled-potion missing discard, uncovered Search edge, and other unexpected missing-edge cases remain fail closed;
- every actual Search root edge remains covered;
- STSRL-009 deterministic audit passes all twelve reviewed predicates;
- no-potions Search edge surface/work/RNG semantics remain unchanged;
- v1 is not silently reinterpreted and unknown schemas fail closed;
- no hidden/private information, fallback, retry, alternate Search, or reseed path is introduced;
- T101 scientific ranking/admission semantics are not silently changed;
- no support census, 20-case fidelity diagnosis, 70-case projection replay, N>2 convergence, training, promotion, or complete-run claim occurs.

The intended successful terminal is:

`NATIVE_CONFIGURATION_AWARE_ROOT_MAPPING_ACCEPTED`

## Failure / Incomplete Conditions

Use `SOURCE_LINEAGE_INVALID` if the target cannot be proved to descend from the accepted line, reviewed head is absent, reviewed-head-to-merge tree equivalence fails, or active ref does not resolve to the pin.

Use `NATIVE_CAPABILITY_VERIFICATION_FAILED` if lineage is valid but clean build/import, v2 schema, nullable semantics, fail-closed controls, deterministic audit, Search invariance, or production-injection isolation fails.

Use `VERSIONED_CONTRACT_COMPATIBILITY_INVALID` if accepting v2 requires silently redefining v1, accepting unknown/ambiguous null rows, or weakening the historical fail-closed contract.

Use `INFORMATION_SAFETY_CONTRACT_INVALID` if new accepted surfaces expose hidden/private native information or exception prose as scientific classification data.

Use `INCOMPLETE` if required source identity or verifier evidence cannot be produced.

No non-success terminal authorizes a support/convergence re-entry.

## Explicit Non-Claims

T110 does not establish:

- that all 323 historical T108 rows now pass end-to-end STSRL admission;
- that the 20 public-fidelity failures are repaired or irrelevant;
- that the 70 projection-parity failures are repaired;
- T101 cohort sufficiency;
- particle-count convergence;
- action-value/rank convergence;
- potion-search correctness or efficacy;
- Search/controller/model improvement;
- complete-run improvement;
- T034 completion;
- T063/T066 activation.

## Out Of Scope

Do not perform or authorize in T110:

- edits to `sts_lightspeed`;
- enabling potion Search or changing `include_potions` policy;
- fake/placeholder Search edges or imputed values;
- replay of the exact 323 T108 mapping-stage identities;
- diagnosis/replay of the separate 20 public-fidelity identities;
- replay of T104 Part-A projection-parity failures;
- scientific redefinition of the T101 ranking/action domain;
- N>2 particle convergence;
- cross-particle action selection/controller behavior;
- training, controller promotion, complete-run evaluation;
- T034 closure or T063/T066 activation.

## Successor Meaning

Only a successful `NATIVE_CONFIGURATION_AWARE_ROOT_MAPPING_ACCEPTED` terminal permits Planner to publish a bounded scientific support-contract re-entry.

That successor must explicitly decide how T101-style admission and convergence distinguish:

- the full public legal-action identity surface; and
- the configured Search-evaluated action subset.

The successor should use the smallest deterministic N=2 witness needed to test that contract before any larger cohort execution. The separate 20 `PUBLIC_FIDELITY_VALIDATION_FAILURE` cases remain an independent lane and must not be silently folded into the root-mapping repair.

## PR Report

The final PR report must state:

- publication base and exact approved spec head;
- old and new native pins;
- reviewed native head and durable review comment ID;
- lineage/tree-equivalence/ref proof;
- exact verifier-built native source identity;
- v2 bridge/root/mapping/diagnostic schema identities;
- v1 compatibility strategy;
- STSRL-009 audit result for all twelve predicates;
- nullable/no-value and fail-closed negative-test results;
- Search surface/work/RNG invariance evidence;
- tests/commands actually run;
- terminal classification and bounded interpretation;
- confirmation that no scientific support replay, fidelity diagnosis, convergence, training, or promotion occurred.
