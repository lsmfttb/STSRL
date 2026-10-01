# T110 exact-source and versioned-contract verification

This factual record accompanies [T110](../../T110-native-configuration-aware-root-mapping-source-acceptance.md)
on [STSRL PR #128](https://github.com/lsmfttb/STSRL/pull/128). Publication base:
`f59fcbe78a0d49dfedc54386bc618d13a6f0e7b5`; approved contract:
`a4f21b1463a6781cb13df9fc44f02015abef44ad`, Maintainer `SPEC APPROVED`
comment `5933071940`. The bounded implementation result is
`NATIVE_CONFIGURATION_AWARE_ROOT_MAPPING_ACCEPTED` if the independently
reviewed PR content lands. This is capability acceptance, not a population
or scientific-support result.

## Exact native identity

The manifest selects `https://github.com/lsmfttb/sts_lightspeed.git`, branch
`stsrl/main`, ref `refs/heads/stsrl/main`, exact commit
`6496fc1c7e629a374b72bd94f7fd29afe29c7f62`. The canonical verifier fetched
the active integration ref, required it to resolve exactly to that pin, and
independently proved the actual Git graph:

- first merge parent / previous accepted pin:
  `1458522294d967e8985e1fd52cc15d7ebe7f2acd`;
- second parent / reviewed native PR #26 head:
  `d26f557bf33639f921e5cf16c220d0e1e357f6f2`;
- both parents are ancestors of the selected commit;
- reviewed and merged trees both:
  `3e5e3d2c73e70bce2a726a563208c1fbb66c5c0c`, with a quiet reviewed-to-merge
  diff. Native independent review remains comment `5931892904`.

The previous-pin-to-new-pin file delta is confined to the binding/report
construction, native audit/smoke, and documentation. No native Search,
sampler, or fidelity implementation file changed. STSRL made no edits or
commits to the native repository.

## Canonical disposable build and retained attempts

The canonical command for successful attempts 2 and 3 was:

```text
env STSRL_LIGHTSPEED_BUILD_JOBS=16 bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed-t101-97f59b6
```

The last argument supplies Git objects only, not its old checkout/binary.
The verifier fetched current source, created the fresh detached worktree
`/tmp/stsrl-lightspeed-source.XVAqHp`, built in its
`build-stsrl-source-py` directory, and checked imported-module containment.
It removed inherited `PYTHONPATH`; every native/API smoke used the module
built there. Pinned submodules were materialized from exact Git archives:
JSON `0b345b20c888f7dc8888485768e4bf9a6be29de0`, pybind11
`d03662f0984f652b60e7ddce53d3868002275197`. Compiler: GCC 15.2.0;
interpreter: CPython 3.14.4; native compilation workers: 16.

The successful attempt was run on STSRL producer
`d76921e32bc7638fd6bd558033d7a3f4b94d1d09`, started
`2026-10-01T14:28:17.630764Z`, ended `2026-10-01T14:28:44.079109Z`, elapsed
26.448345 seconds, `SUCCEEDED`, exit 0. Supervisor/target 438/439 were
absent after termination. The verifier cleaned its disposable worktree.
Subsequent changes added exact runtime-identity compatibility and factual
documentation. The later Maintainer-requested v2 diagnostic completion
repair was reverified in the separate successful attempt 3 below.

Retained local evidence root:
`D:\DeadlyCatCoding\STSRL\artifacts\t110-source-acceptance`.
Successful attempt files and SHA-256:

| Relative path | Bytes | SHA-256 |
|---|---:|---|
| `canonical-verifier-attempt-2/status.json` | 904 | `763176072d80b577552302d3e7ab4e2da57751098ed9c465201ebcdea0d1a743` |
| `canonical-verifier-attempt-2/stdout.log` | 7383 | `50818917967272d9fc727540ab868c6abd3b3f77b7beadd7fabd351dfdefbe25` |
| `canonical-verifier-attempt-2/stderr.log` | 610 | `852484fb757818002d98696e161b5a2cd7b15650710e083d210235c66d43f8fc` |

Attempt 1 is preserved separately. Its exact-source build succeeded, but
STSRL's initial v2 validator rejected `root_evaluation.model_calls == null`.
Source inspection confirmed that aggregate field intentionally remains null;
the concrete model-call count belongs to typed work counters. The correction
requires null for this v2 aggregate field, leaves v1 validation unchanged,
and never imputes numeric zero. Attempt 1 ended `FAILED`/exit 1; its output
does not substitute for the passing attempt 2.

### Post-review empty-surface completion repair

Maintainer review found that all-zero v2 completion counts could incorrectly
pass despite the native fail-closed `no_public_legal_action_surface` branch.
Only v2 `completed` now rejects zero public legal occurrences. A regression
test also proves the valid v2 empty-surface failure remains accepted and the
historical v1 all-zero behavior is unchanged.

The changed diagnostic helper is exercised by the STSRL-owned STSRL-008
canonical smoke, so canonical attempt 3 ran on repaired implementation
producer `98d72e11ba67e75981dd43b98ce7ee2af488336a`. It fetched and rebuilt
the same exact native pin in `/tmp/stsrl-lightspeed-source.rvJgFk`, started
`2026-10-01T14:55:06.620048Z`, finished `2026-10-01T14:55:50.116695Z`, and
passed in 43.496647 seconds (`SUCCEEDED`, exit 0). All previously required
native/API/sampler/visibility/STSRL-006/007/008/009/Search gates passed again.
Supervisor/target 457/458 were absent after termination; stdout/stderr and
disposable build/import evidence were inspected. No native edit occurred.

| Relative path | Bytes | SHA-256 |
|---|---:|---|
| `canonical-verifier-attempt-3/status.json` | 904 | `fe99ba620edf30a8353431ef5202af74ea7dabaec29cb23400ba3136e7169425` |
| `canonical-verifier-attempt-3/stdout.log` | 7383 | `57ebc441ddf3c8607fd8175a01509702caafcf4ca3bb7d802cbdf68de211e339` |
| `canonical-verifier-attempt-3/stderr.log` | 610 | `852484fb757818002d98696e161b5a2cd7b15650710e083d210235c66d43f8fc` |

Earlier source acquisition completed the exact pinned submodules, but its
volatile `/tmp/stsrl-t110-native-source` directory later disappeared across
a WSL boundary before any canonical run launched. No clone/submodule process
remained when recovery began. Recovery used verified cached Git/submodule
objects and the fresh canonical detached build above. This is not treated
as a native scientific failure or evidence from an unverified old binary.

## Version and exclusion contract

The generic bridge entry point explicitly dispatches recognized v1/v2;
dedicated v1 and v2 paths remain independently callable. Canonical current
source checks require v2 specifically, so a v1 fallback cannot pass. Unknown
schemas fail closed. Current accepted identities are:

- bridge `native-battle-public-particle-search-v2`, API
  `StepSimulator.sample_hidden_future_particles_search.v2`;
- root `native-battle-search-root-v2`;
- mapping `native-search-root-occurrence-equivalence-v2`;
- diagnostic `native-root-occurrence-mapping-diagnostic-v2`.

Public identities/order are retained. Exclusion is accepted only for battle
`potion`/`potion_discard` rows with safe projection `input_state == PLAYER_NORMAL`,
bridge and root `include_potions is False`, reason `include_potions_false`,
no Search tree, null edge/source/mode/evaluation/mean, and integer zero visits.
Mapping rows also require null edge/mode/source/edge-occurrence count. This
matches the reviewed native predicate `PLAYER_NORMAL && ActionType::POTION &&
!includePotions`; potion discard shares that native action type. No additional
private input-state surface was introduced.

Direct and duplicate-card searched rows require concrete covered edges and
correct source-action/mode. Every actual Search edge is covered; searched +
excluded equals classified equals public legal count. Diagnostic v2 counts
preserve the seven fail-closed subreasons. Null edges alone never imply
exclusion. Root and mapping row field allowlists, diagnostic allowlists, and
existing public-projection validation reject unsafe extras. Public values
are never synthesized for excluded actions.

T077/T085 add only the named exact T110 current-runtime identity to their
finite allowlists. T076/T085 historical artifact anchors and T107 identity
remain immutable, with positive historical and unknown-pin negative tests.
T101 admission/ranking code is unchanged: finite-value scientific treatment
of excluded rows still requires a separately approved successor contract.

## Required verification results

| T110 items | Executed evidence / outcome |
|---|---|
| 1 | Manifest parser/exact-pin/capability tests passed. Historical T099/T107 provenance retained; new T110 capability explicit. |
| 2–4 | Fresh remote-ref, parent ancestry, reviewed/merged exact tree, detached source build/import passed in canonical attempt 2. |
| 5–6 | Native API smoke passed; T096 bounded 8-particle sampler witness and all 26 visibility predicates passed. |
| 7 | STSRL-006 deterministic bridge audit: all 8 predicates true. |
| 8 | STSRL-007 stage audit: all 7 predicates true; Search setup/execution remain before mapping. |
| 9 | STSRL-owned STSRL-008 exact-source diagnostic/isolation/audit passed under diagnostic v2, including all seven failure witnesses. Active `PLAYER_NORMAL` battle reached within accepted 32-action cap before N=2 bridge call. |
| 10 | STSRL-owned STSRL-009 exact-source configuration/isolation/audit passed; all 12 predicates below true. |
| 11–13 | Independent strict v2 searched/excluded/null/count/order controls and unchanged strict v1 tests passed; unknown schemas rejected. |
| 14–15 | Positional/keyword production failure-injection attempts rejected with TypeError; audit does not accept caller injection. Exact sanitized field contracts and negative private-field controls passed. |
| 16 | Exact-source Search-v2 tree geometry and native T079 state-utilization checks passed; no replacement Search path. |
| 17 | Final repaired focused tests 122 passed; compileall, changed-file Ruff and diff checks passed. Full-suite/baseline qualifications below. |

All STSRL-009 predicates were independently required as boolean true by
the STSRL-owned audit validator (missing/false/null/integer-one rejected):
`potion_use_excluded`, `potion_discard_excluded`,
`public_action_order_preserved`, `searched_actions_preserved`, `no_fake_values`,
`mapping_schema_versioned`, `diagnostic_v2_counts_correct`,
`required_missing_non_card_fails_closed`,
`enabled_potion_missing_discard_fails_closed`, `uncovered_edge_fails_closed`,
`search_surface_and_work_unchanged`, `all_search_edges_covered`.
The native invariance witness covers Search surface, visits/evaluations/work,
and RNG state; the prior STSRL-006/T096 predicates provide separate
sampler/public-fidelity regressions.

## Repository checks and honest baseline qualifications

Final focused command covers T110, T099, T107, source manifest, T105, T096,
T098, T077 and task-doc tests: **122 passed**, including the new empty-surface
regression (the preceding implementation check had 121 passed).
`python -m compileall -q src tests`, shell syntax checking, and
`git diff --check` passed. Ruff 0.16.5 touched files pass except the same
three inherited TRY004 diagnostics in `lightspeed_source.py`; normalized
full-repository comparison against publication base is 529 diagnostics on
each side, with zero added diagnostic/path/message tuples. Formatting is
24 inherited files on each side, no added formatting debt.

Unrestricted Windows collection has four inherited environment errors:
two T085 modules require unavailable torch, and two T092 execution modules
require Linux `resource`. Excluding those four modules, the final Windows
suite before the narrow empty-surface repair was **1574 passed, 39 skipped,
10 failed** in 91.90 seconds. All ten
failure nodes reproduce on exact publication base `f59fcbe`:

- five T088 construction/progressive-bias tests retain historical exact pin
  `20a6c2b` and reject the already newer runtime;
- one Non-Combat regeneration-command legacy path assertion;
- one T092 canary root-mismatch assertion;
- three T104 Linux-fork tests cannot execute on Windows.

The first full suite additionally exposed two source-allowlist regressions;
the named T110 compatibility additions repaired both. Final tests introduced
no new failure node. This is not an all-green full-suite claim. Raw logs are
`repository-tests.log`, `repository-tests-final.log`,
`baseline-failure-reproduction.log`, and `focused-tests-final-2.log` under
the evidence root; the repaired focused result is retained separately in
`focused-tests-empty-surface-repair.log`. Changed Python/tests pass applicable focused checks;
historical unrelated failures were not broadened into this task.

## Bounded interpretation

Only deterministic source/capability/native API smoke ran. No T101/T104/T106/
T108 population replay, 20-case public-fidelity diagnosis, 70-case projection
replay, N>2 Search/convergence, training, promotion, or complete-run evaluation
ran. The 8-particle inherited T096 sampler capability witness is not a Search
or scientific convergence run. No support restoration or controller-quality
claim follows from this acceptance. Planner owns the separately scoped
configured-Search-domain successor and final scientific/architecture decision.
