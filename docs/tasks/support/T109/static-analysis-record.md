# T109 static action-domain audit

This record is the static-first result for T109 / draft PR #127 on branch
`planner/t109-static-first-root-mapping-domain-audit`. Publication base:
`main @ 6ba76017463c9f7cc11686a2c655f78203ce799a`. Exact approved contract
head: `db7f4b1aa4f9492c2fc2a7db1fae39c6589e985c`. It uses the exact T108
retained population and the accepted native source pin. No simulator, replay,
census, witness, telemetry, native edit, repair, convergence, training, or
promotion was started.

## Input qualification

The read-only T108 root was
`D:\DeadlyCatCoding\STSRL\artifacts\t108-root-occurrence-mapping-subreason-diagnostic-41a789a\full-323-attempt-2\`.
The four artifact bytes match the accepted T108 identities:

| Artifact | Schema | SHA-256 |
| --- | --- | --- |
| `t108-candidate-mapping-subreasons.json` | `t108-root-mapping-subreason-rows-v1` | `bbd8db3dafcfcb729f198b1f5c7c86d6d1156ef0041ed74e8d00965e0a1f8c26` |
| `t108-aggregate-report.json` | `t108-root-mapping-subreason-report-v1` | `df61a122d7d01d9aa89fccfefe578c09e0c304a2841887146aedf67af5c2bbd6` |
| `t108-execution-record.json` | `t108-execution-record-v1` | `8faf47cf79807bde3ef70182ad798ecb27a6d670cf2ae8dc70a2fbce1b7a64fb` |
| `t108-retention-manifest.json` | `t108-root-mapping-subreason-retention-manifest-v1` | `35f8e53f75f98134922a7725d25986696678f102ff1808000c2e81fc934fa8e2` |

The candidate file contains exactly 323 rows. Its hash is the accepted T108
candidate identity, so the retained order and rows are unchanged; the accepted
[T108 execution handoff](../T108/implementation-and-execution.md) documents
the ordered identity digest
`fa798b1af6f88e542a09527703f89eb81310c882377938be2ed10056ec05cb38` and
A/B/C counts `84/174/65`. Only the accepted safe diagnostic fields and the
frozen `include_potions` configuration value were summarized below. No row
identity, raw action value, private Search payload, hidden state, RNG value, or
exception prose was read out or reproduced here.

The exact native source was read from
`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1458522294d967e8985e1fd52cc15d7ebe7f2acd`, matching
`docs/sts_lightspeed_source_manifest.json` and the T109 contract. The local
native repository's checked-out branch was unrelated and dirty; it was left
untouched. Source inspection used `git show <pin>:<path>` and the commit object
was present.

## Accepted safe-field cross-tabs

All 323 rows have structured classification source and the accepted
`missing_non_card_direct_search_root_match` subreason. The safe occurrence
metadata is complete for both required discriminators. T107 defines
`public_action_kind` and `direct_match_multiplicity` as occurrence metadata and
validates them against closed vocabularies before T108 retains them
(`src/sts_combat_rl/sim/t107_native_root_mapping_observability.py:39-46,204-219`;
`src/sts_combat_rl/sim/t108_mapping_subreasons.py:360-413`):

| Safe field | Present | Missing | Cross-tab |
| --- | ---: | ---: | --- |
| `public_action_kind` | 323 | 0 | `potion`: 322; `potion_discard`: 1 |
| `direct_match_multiplicity` | 323 | 0 | `zero`: 323 |
| `mapping_subreason` | 323 | 0 | `missing_non_card_direct_search_root_match`: 323 |
| `input_state` | 0 | 323 | no safe input-state field was retained |

Pair cross-tab: (`potion`, `zero`) = 322; (`potion_discard`, `zero`) = 1.
There are no card, End Turn, single-card-select, or multi-card-select
counterexample kinds. `input_state` is missing retained coverage for all 323
rows; this is not evidence that the input state varied. Separately, source
shows that the public producer can emit these potion action kinds only from its
`PLAYER_NORMAL` branch, and `isValidPotionAction` rejects other states. This is
a source-derived producer-branch mapping, not retained per-row state metadata.

The frozen expected and observed `include_potions` value is `false` on all 323
rows (0 missing). Thus the safe action-kind/multiplicity fields, not the common
T108 subreason label alone, discriminate the proposed mechanism across the
whole accepted population.

## Source-grounded action-domain matrix

Source references below all resolve at the exact native pin named above.
“Predicted branch” is the branch `validateSearchRootMapping` takes if the public
occurrence has no direct root-edge match. Predictions for the observed rows are
deductive from source plus the frozen configuration; unobserved classes are
listed only to bound the audit.

| Action class | Public legal-action producer | Search root-edge producer and gate | Mapping expectation and absent-edge branch | Finding |
| --- | --- | --- | --- | --- |
| `PLAYER_NORMAL` card | `enumerateBattleActions` creates valid card actions for hand sources and applicable targets; `Action::isValidAction` checks outcome, state, play permission, and card playability (`bindings/slaythespire.cpp:224-258`; `src/sim/search/Action.cpp:104-125,226-250`). | `enumerateActionsForNode` calls `enumerateCardActions`; Search filters for playable cards and collapses adjacent mechanical duplicates (`src/sim/search/BattleScumSearcher2.cpp:686-692,757-811`). | Direct action match is tried first. A missing nonduplicate is classified by card-specific duplicate/representative branches, not the non-card subreason (`bindings/slaythespire.cpp:2281-2340`). | No card kind appears in the 323 rows. The card-only canonicalization cannot explain or contradict the observed non-card classes. Deductive source behavior; no observed counterexample. |
| `PLAYER_NORMAL` potion use | `enumerateBattleActions` iterates potion slots and valid use targets (`bindings/slaythespire.cpp:224-274`); this producer branch is restricted to normal input, and validity checks the undecided outcome and potion use (`src/sim/search/Action.cpp:66-102,226-236`). Action-kind labels are produced by `battleActionKind` (`bindings/slaythespire.cpp:185-198`). | `enumerateActionsForNode` calls `enumeratePotionActions` only when `includePotions` is true (`src/sim/search/BattleScumSearcher2.cpp:686-694`); the helper materializes Search potion edges (`src/sim/search/BattleScumSearcher2.cpp:813-851`). | The mapper requires a direct edge match for every non-card public occurrence. With `includePotions=false`, no Search potion-use edge is produced, so multiplicity is zero and the predicted branch is `missing_non_card_direct_search_root_match` (`bindings/slaythespire.cpp:2233-2240,2271-2279`). | 322 observed rows; all have multiplicity zero and the predicted subreason. Deductive under the frozen setting; the input state is not retained per row. |
| `PLAYER_NORMAL` potion discard | The public enumerator constructs and validates an explicit discard occurrence for each potion slot (`bindings/slaythespire.cpp:224-274`; `src/sim/search/Action.cpp:66-102`); the producer branch is restricted to normal input. Action-kind labels are produced by `battleActionKind` (`bindings/slaythespire.cpp:185-198`). | The same `includePotions` gate controls the entire Search potion helper. When enabled, that helper does not generally mirror public discard enumeration; its comment says it omits discarding a potion that can be used (`src/sim/search/BattleScumSearcher2.cpp:692-694,813-851`). | Under the frozen false setting there is no Search potion edge, so the non-card direct-match branch predicts zero and `missing_non_card_direct_search_root_match`. | 1 observed row; multiplicity zero and predicted subreason. Deductive under the frozen setting; the input state is not retained per row. Enabled-potion parity remains a separate design question, not an alternative explanation for these rows. |
| `PLAYER_NORMAL` End Turn | `enumerateBattleActions` adds End Turn when valid (`bindings/slaythespire.cpp:238-241`); validity requires an undecided outcome and `PLAYER_NORMAL` (`src/sim/search/Action.cpp:226-250`). | `enumerateActionsForNode` adds End Turn unconditionally in the normal-state branch (`src/sim/search/BattleScumSearcher2.cpp:690-696`). | Same action type has a direct root edge in this state. If it were absent, the mapper would take the non-card zero-match branch. | No End Turn kind appears. Under the same root state, source predicts a direct match. |
| `CARD_SELECT` single/multi selection | The public enumerator returns `Action::enumerateCardSelectActions` for `CARD_SELECT` (`bindings/slaythespire.cpp:230-232`; `src/sim/search/Action.cpp:477-503`). | Search calls its own card-select enumerator in the `CARD_SELECT` branch (`src/sim/search/BattleScumSearcher2.cpp:698-700,865-1021`). | Selection action types are non-card for the mapper; an absent direct edge would take `missing_non_card_direct_search_root_match`. | No safe action kind is a card-select form. No T108 row reaches this branch; separate public/Search helper parity is not needed to explain the observed classes. |
| `PLAYER_NORMAL` potion gate | The public legal surface includes valid potion-use and discard occurrences regardless of Search configuration (`bindings/slaythespire.cpp:260-271`). | `includePotions` is copied from the bridge argument into the Searcher (`bindings/slaythespire.cpp:2521-2528`); false skips `enumeratePotionActions` entirely (`src/sim/search/BattleScumSearcher2.cpp:690-694`). | The mapper's direct requirement is unchanged by the Search gate; each excluded public non-card occurrence yields zero matches and the exact observed subreason (`bindings/slaythespire.cpp:2233-2240,2271-2279`). | Expected and observed T108 configuration is false on all rows; this is the common deductive mechanism for all 323. |
| Direct non-card mapping invariant | The input is each occurrence in the ordered public legal-action surface (`bindings/slaythespire.cpp:2205,2233-2235`). | The input is each root edge already produced by Search (`bindings/slaythespire.cpp:2235-2240`). | A direct match compares the common native action representation; one match maps, multiple matches fail as ambiguous, and zero for any action type other than `CARD` emits `missing_non_card_direct_search_root_match` (`bindings/slaythespire.cpp:2235-2279`). | This is the exact branch and zero multiplicity observed for every row. The mapper has no non-card representative/canonicalization path. Deductive. |

### Other candidate mechanisms checked

- `validateSearchRootMapping` calls the public enumerator on `item.state`,
  compares each public occurrence to root edges by the native action
  representation, and has no non-card canonicalization fallback
  (`bindings/slaythespire.cpp:2200-2240,2271-2280`). The card representative
  fallback is explicitly card-only.
- The Searcher copies the same `item.state` into its root state
  (`src/sim/search/BattleScumSearcher2.cpp:242-244`). Root edges are expanded
  from that root before an edge executes on a copied state (`:397-420`); the
  bridge then validates using the unchanged `item.state`
  (`bindings/slaythespire.cpp:2539-2558`). No transition between distinct
  states explains the missing potion edges.
- Both surfaces use the common native `Action` type and constructor family
  (`src/sim/search/Action.cpp:12-35`). The observed false configuration omits
  the Search edges altogether, so a representation/identity mismatch is not
  needed. No actual action-bit values were consumed or retained by this audit.
- Public validity checks explain which occurrences enter the mapping domain;
  they cannot remove the already-enumerated potion occurrences from the public
  side. Search-side card filtering and duplicate canonicalization are
  card-specific. Search-side potion validity/target handling is behind the
  disabled gate. Neither is a competing explanation for the present observed
  zero matches.

## Static sufficiency decision

Proposed scientific terminal: `ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED`.

The Static Sufficiency Gate passes at the claimed, bounded level:

1. All 323 classified rows contain `public_action_kind` and direct multiplicity.
2. Both observed kinds are potion classes whose public producer is source-
   restricted to `PLAYER_NORMAL`; T108 did not retain per-row input state.
3. `include_potions=false` directly excludes both classes from Search root
   enumeration.
4. The mapper still requires direct matches for every non-card public
   occurrence and emits the observed subreason with multiplicity zero.
5. No retained action-kind counterexample exists.
6. Since the Search edge is excluded, no action-identity/representation
   hypothesis is needed to account for the observed rows.

This establishes a configured public-domain/Search-root-domain contract
mismatch for the exact accepted T108 323-row population. It does not establish
a game-mechanics defect, a correct repair, repair efficacy, Search improvement,
particle convergence, or a controller result. No dynamic witness is justified
for this mechanism. The architecture choice remains open: filter the mapped
public domain, preserve identities for valid but unsearched root actions, or
change the mapping invariant. Enabling potion Search alone is not accepted as a
repair; enabled-potion parity must be assessed separately if a later approved
task chooses that route.

## Lifecycle draft and execution boundary

The following updates are proposed only, pending Planner scientific
acceptance and Maintainer exact-head review. `docs/current_status.md` and
`docs/tasks/ARCHIVE.md` remain the accepted-main projection/registry until that
approval; no accepted lifecycle state is changed by this PR draft.

Proposed archive lookup after acceptance:

> T109: DONE; `ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED` on the exact
> T108 323-row population under frozen `include_potions=false`; all 323 safe
> action kinds are potion-use/discard and all direct multiplicities are zero;
> source/configuration mismatch established statically, with no witness,
> repair, or promotion claim.

Proposed current-status addition after acceptance:

> T109's static audit establishes that the exact 323 accepted T108 mapping
> failures are public potion occurrences excluded from Search root enumeration
> by frozen `include_potions=false`, while the mapper requires a direct
> non-card root match. This is a bounded configured action-domain mismatch;
> no dynamic witness or repair was performed, and the repair architecture
> remains open.

Execution boundary: simulator or large job started: **NO**. Contract or native
identity changed: **NO**. No unauthorized replay, telemetry expansion,
convergence, training, or promotion occurred. New artifacts are limited to
this compact record; the four T108 artifacts remain read-only and untouched.

## Verification

- `python -m pytest tests/test_task_docs.py -q`: 7 passed.
- `git diff --check`: passed.
