# T107 native root-mapping observability source-acceptance execution

This record accompanies the [T107 contract](../../T107-native-root-mapping-observability-source-acceptance.md)
on STSRL PR #124. The publication base is
`d1456a7bd1f8182d3bb6b611a537dda51c4c9075`, the approved specification is
`8182e1ab0b082672091b6943b5a21e15fc90409a`, and the final implementation
producer, including the bounded smoke-fixture repair, is
`cd6359c9c56f370e11864627d5412701f0adb522`. The source/capability result is
`NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED` if this exact PR content
lands.

## Native source identity and lineage

The canonical manifest pins
`https://github.com/lsmfttb/sts_lightspeed.git` at
`refs/heads/stsrl/main` / `1458522294d967e8985e1fd52cc15d7ebe7f2acd`.
Independent checks against the native Git graph establish that the previous
accepted pin `5afae22def0c69657b0139bfa21306aebac831af` is an ancestor of the
merge, reviewed native PR #24 head
`264dcacaf9236cd133d8e9147186ad3698b42a3f` is included in the merge, and the
reviewed head's tree is identical to the merged result. A fresh remote ref
query resolved `refs/heads/stsrl/main` exactly to the pinned commit. The
canonical verifier independently checked the prior-pin, reviewed-head, and
T107-merge relationships before building.

## Canonical disposable-source verification

The final verifier attempt ran on implementation producer
`cd6359c9c56f370e11864627d5412701f0adb522` through
`scripts/verify_lightspeed_source.sh`. It cloned the integration source without
checkout to `/tmp/stsrl-t107-native-inspect.attempt-5`, fetched the exact
`stsrl/main` result, verified its lineage, then created and built a fresh
disposable worktree. The command removed inherited `PYTHONPATH` and used eight
native build jobs. The build used CPython 3.14.4 and pinned submodules:

- `json`: `0b345b20c888f7dc8888485768e4bf9a6be29de0`;
- `pybind11`: `d03662f0984f652b60e7ddce53d3868002275197`.

The build/import check, native API smoke, T096 visibility and sampler checks,
STSRL-006 bridge audit, Search-v2 tree geometry and state-utilization checks,
T105 stage-observability checks, and T107 smoke all passed. The final log
contains `STSRL-008 exact-source diagnostic, isolation, and native audit
passed` followed by `clean sts_lightspeed pinned-source build passed`. The
T107 smoke reached a `BATTLE` snapshot with `battle_active is True` and
`battle_input_state == PLAYER_NORMAL` within the exact 32-action cap used by
the accepted native API smoke before calling the two-particle bridge. Its
successful trace reported `mapping_completed`; it validated the accepted
semantic bridge report, production-injection rejection, diagnostic schema,
and all 13 native deterministic-audit predicates, including the seven
fail-closed mapping subreasons. The verifier's exit code
was zero, and its disposable build/worktree was cleaned afterward. No T106
population rows were replayed and no native source was modified.

Attempt 4 is retained as a diagnosed non-evidence failure: the native build and
prior capability checks passed, but the T107 smoke invoked the bridge before
entering battle and stopped with `STSRL-006 particle Search requested outside
battle`. The fixture now advances through legal entry actions under the
bounded, tested 32-action limit. Earlier attempt directories and logs remain
preserved as audit history; none is relabeled as the successful final run.

## Verification and limitations

On the final implementation producer, independent Maintainer checks passed:

- 34 focused manifest, T105, and T107 tests;
- changed-file Ruff check and format check;
- changed-file Python compile check;
- `git diff --check`.

The full WSL pytest suite completed in 324.08 seconds with 1,637 passed,
10 failed, and 2 skipped (one existing multiprocessing deprecation warning).
The ten failures are the same nodes independently reproduced on the
unmodified publication-base `main`: one WSL-mount path fixture, five T088
historical-native-identity fixtures, one fixed WSL-command expectation, and
three T092 fixture/assertion failures. The full suite is therefore not
reported green; no new failure was observed. A repository-wide Ruff comparison
performed on the prior implementation head found 528 diagnostics on both the
task head and base with normalized delta zero. The only later Python changes
are the smoke fixture and its test; both pass Ruff and formatting on the final
implementation producer. The repository's existing full-format limitations
were also unchanged; no changed file was among the previously identified
formatting files.

Retained canonical-verifier evidence under
`artifacts/t107-native-root-mapping-observability-source-acceptance/canonical-verifier-attempt-5/`:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `status.json` | 1,143 | `d2b9f1636d6de5332154bf5b25b237e1519dfb6985bba7cfa3e7c369a62fcfb2` |
| `stdout.log` | 6,790 | `ea0d1b2e9bba6ba65161ed08257eb9b50ee727985e8118d32d7bc62553588e6d` |
| `stderr.log` | 956 | `a1b61f92a7edcb2d30023825193b58c031845c7379133e492da4c06afca55c2f` |

The detached job ran from `2026-09-30T06:25:24.014014Z` to
`2026-09-30T06:36:28.115502Z`, with exit code 0. Attempt 5 is the accepted
verifier evidence; prior attempts remain available for lifecycle audit. No
simulator population, scientific cohort, convergence, training, or promotion
job was run.

## Terminal meaning and boundary

T107 accepts only the exact native STSRL-008 root-occurrence mapping
subreason-observability capability and its provenance. It does not identify
the mechanics root cause of any T106 case, establish a repair, or authorize a
323-row mapping diagnostic or the separate 20-row public-fidelity diagnosis.
Either diagnostic requires its own later Planner-published task contract.
