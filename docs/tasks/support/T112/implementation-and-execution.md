# T112 implementation and execution evidence

## Current lifecycle status

The corrected Stage-2 attempt 4 at implementation producer head
`accf76e50d2572ede5c6d00666560b46c47cc5b5` completed successfully and was
finalized as `CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED`: the exact T101
population (A/B/C 93/192/128) yielded eight admissions in each stratum after
27 fresh attempts (A/B/C 9/8/10). Three searched-value exclusions remained;
no stratum exhausted. The final report SHA-256 is
`d14b67a1f3f76461cb2a356e52df2199c901d09b23c97f80379ac5293bf6b4c9`, and the
terminal retention manifest SHA-256 is
`cd23575eec8f3ce8d95981534312adf7f05cccb3f6cf4ceb9391c5541b1980fb`.

The prior Stage-2 attempt 3 remains preserved as execution evidence only. The
exact-head Planner review in PR comment
[5964590261](https://github.com/lsmfttb/STSRL/pull/130#issuecomment-5964590261)
rejected its `CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT`
classification because 385 `public_projection_parity_failure` rows compared
different schemas. Attempt 3 contributed no rows to attempt 4 and its report,
rows, logs, and retention manifest remain unchanged.

## Preserved attempt 3 observation (not terminal)

The exact T101-ordered 413-candidate population was re-entered at implementation
head `15d9f1c4a229996d93d2c1984404d3bce9d39998` under approved specification
commit `2b45eab755ee0b528b7816d0f2b4089095c0776a`. All three strata exhausted
before reaching eight admissions: A `0/8` after 93 attempts, B `0/8` after 192,
and C `0/8` after 128. No candidate was admitted.

| Exclusion | A | B | C | Total |
| --- | ---: | ---: | ---: | ---: |
| `public_projection_parity_failure` at `bridge_to_restored_projection_parity` | 87 | 175 | 123 | 385 |
| `accepted_structured_bridge_failure` at `single_n2_search_v2_bridge_call` | 5 | 15 | 0 | 20 |
| `searched_value_unavailable_nonfinite_or_unvisited` at `strict_t110_configured_search_validation` | 1 | 2 | 5 | 8 |
| Total attempted | 93 | 192 | 128 | 413 |

The process completed successfully and these counts describe only attempt 3;
they are not a valid T112 support classification. Planner review found that the
385 exclusions were produced by comparing a T014 `NativePublicProjection`
restore/context payload (`native-public-projection-v1`) with the bridge's
T096/T099 battle-information anchor (`native-battle-public-information-v1`
or `-v2`). Those payloads are different contracts and are not expected to be
equal. The repaired ordered-action parity check therefore merely moved these
rows to the next, invalid cross-schema comparison. The retained attempt did not
retroactively admit any candidate, and none of its rows may be reused as
admissions for the correction.

Planner authorized a narrow T112 correction: retain the T014
restore/context/candidate parity checks, obtain the restored direct T096
projection through the accepted `t096_public_information_projection`
capability (or existing equivalent), validate it with the existing T096
validator, and compare that like-for-like value against the bridge anchor. Do
not compare T014 `canonical_payload` to the T096 anchor. Add tests proving the
cross-schema comparison is absent, matching direct T096/bridge-anchor values
pass, and T096 field/action/visibility drift fails closed. After exact-head
review and the required stage-specific authorization, run a fresh selector
from original T101 order, stopping each stratum at eight admissions or
exhaustion. The 20 bridge failures and 8 searched-value failures remain
ordinary residuals unless they prevent the required 8/8/8 support result.
Native changes, larger replay, N>2, convergence, training, promotion, and merge
remain out of scope.

## Implementation and witness

The Maintainer reviewed the corrected implementation head and recorded focused
verification: 140 T111/T099/T110/T112 tests, Ruff and formatting checks,
`compileall`, and `git diff --check` passed. No native source was modified.
The accepted native source pin is
`lsmfttb/sts_lightspeed@6496fc1c7e629a374b72bd94f7fd29afe29c7f62`; binary
SHA-256 is
`cdf650362a8178aed1919efb05b2255a8986562d6617e659e8e0dca26583dd3a`.

Stage-1 witness attempt 5, bound to the same implementation producer head,
was finalized as
`N2_WITNESS_SEED_CONTRACT_ACCEPTED`: exactly one native bridge call, zero
retries, matching requested/observed `sampler_seed_input`, valid indexed
native-derived particle seed metadata, and no selector invocation. Its terminal
artifact is
`artifacts/t112-sampler-seed-contract-repair-76d2ff7/witness-attempt-5/t112-witness-terminal.json`
(SHA-256
`62cf5100dd787e582fe989b42e2961ff74c33b44a16bea3b5adffad1a46eb3a0`).

## Preserved Stage-2 attempt 3 (invalid terminal classification)

The separately authorized cohort attempt 3 approval is PR comment
[5961990819](https://github.com/lsmfttb/STSRL/pull/130#issuecomment-5961990819).
It used one worker and one `[0,413)` shard, with A `[0,93)`, B `[93,285)`, and
C `[285,413)`. Frozen settings were replicate 0, `particle_start=0`, N=2,
unguided Search-v2@400, no potions, policy prior/learned leaf value/progressive
bias off, and no retry, reseed, fallback, or substitution. Each of the 413
retained candidate attempts has one native bridge call; no retry was recorded.

The detached job started at `2026-10-02T21:53:16.328991Z` and finished at
`2026-10-03T01:23:55.412564Z`, state `SUCCEEDED`, exit code 0. The resource guard
completed with 12,620 samples, peak RSS 3,630 MiB against an 8,192 MiB limit,
lowest available memory 17,873 MiB against an 8,192 MiB floor, and no tripwire;
the lease was released. The T112 finalizer revalidated the witness, exact-head
authorization, source population, and retained artifact bindings before
writing the final report and retention manifest.

The execution record binds 413 source identities in exact T101 order with
ordered-identity SHA-256
`a99fcd38ea6e5c14190b0964c8ec5a04fc40f501d91ab4409c7205bc8b3677bb`. The
historical T101 native identity is
`97f59b620efe5ee1571f8da298c99d1e21c1149b`; it remains distinct from the
current T112 source pin and binary above. The final report records
`no_retry_or_substitution=true`, `historical_failure_label_preselection=false`,
`historical_t111_attempts_used_for_admission=false`,
`selection_uses_value_or_outcome=false`, and
`no_n_gt_2_or_convergence_execution=true`.

## Preserved attempt 3 artifacts

All paths below are under the ignored artifact root
`artifacts/t112-sampler-seed-contract-repair-76d2ff7`:

| Artifact | Schema | SHA-256 |
| --- | --- | --- |
| Cohort authorization `jobs/t112-cohort-authorization-15d9f1c-attempt-3.json` | `t112-maintainer-stage-authorization-v1` | `cc4807cf5bff3185f43ee4dbf74c2be669b6bad8e5745f028d65c9532e7efeaf` |
| Input qualification `preparation-attempt-4/t112-input-qualification.json` | `t112-input-qualification-v1` | `418e0fbf6ac5de1a7a9eb7d24e1bfdbd003ae9aa66196cba13d4d7a9d7380402` |
| Readiness preparation `preparation-attempt-4/t112-readiness-preparation.json` | `t112-readiness-preparation-v1` | `4a50a7943485d310ca911fc3b8698a732c7b981ed8ea03d6155ba084611d7a68` |
| Cohort candidate attempts `cohort-attempt-3/t112-candidate-attempts.jsonl` | `t112-candidate-attempts-jsonl-v2` | `3b1a3968f2bce077f3587c2910dc996100f57ec06ea0c07face06626b8ccee0e` |
| Cohort admission `cohort-attempt-3/t112-cohort-admission.json` | `t112-configured-search-cohort-admission-v2` | `26b0bc13d13be4046e465bf6affc22c8cdac482b99fb767166b160f3b9de5b36` |
| Execution record `cohort-attempt-3/t112-execution-record.json` | `t112-cohort-execution-record-v2` | `5b71034059871fb0dbf84a73263b0bf1189de91c6b53b48f26aa912b0bb1a052` |
| Final report `cohort-attempt-3/t112-final-report.json` | `t112-final-report-v2` | `beb5204250d0c6092e03e26e56954085e204a1cd1264447988c1538377314350` |
| Terminal retention manifest `cohort-attempt-3/t112-terminal-retention-manifest.json` | `t112-terminal-retention-manifest-v1` | `51f40223ab839967ff5e67f517cbe0712c4357d8234d96e95cc28e4e1bc8ef71` |

The attempt-3 retention manifest binds its own detached status and evidence.
That run remains immutable audit history; its invalid terminal classification
and rows were not reused.

## Corrected Stage-2 cohort attempt 4

The separately authorized attempt 4 is bound to producer head
`accf76e50d2572ede5c6d00666560b46c47cc5b5` and Stage-1 witness attempt 5. Its
approval is PR comment
[5965216719](https://github.com/lsmfttb/STSRL/pull/130#issuecomment-5965216719);
its authorization SHA-256 is
`695a013899a4060ec4549bf9797db14cbfad8583cc00e77c09443f30814db3cd`. The
single worker covered `[0,413)` with A `[0,93)`, B `[93,285)`, C `[285,413)`.
Frozen settings were replicate 0, `particle_start=0`, N=2, unguided
Search-v2@400, no potions, and no retry, reseed, fallback, or substitution.
The job started at `2026-10-03T03:54:06.685677Z` and finished at
`2026-10-03T04:20:41.259308Z` with state `SUCCEEDED`, exit code 0.

Finalization independently verified the exact-head authorization, accepted
witness, T101/T111/native provenance, full 413-row source order, strict T111
candidate validation, cohort/attempt records, direct like-for-like T096 public
projection parity, and completed resource guard. The ordered-identity
SHA-256 is
`a99fcd38ea6e5c14190b0964c8ec5a04fc40f501d91ab4409c7205bc8b3677bb`. The run
made 27 unique attempts (A/B/C 9/8/10) and admitted 8/8/8; every row records
one native bridge call, zero retries, and passing `public_projection_parity`.
Three candidates were excluded as
`searched_value_unavailable_nonfinite_or_unvisited` at
`strict_t110_configured_search_validation`. No stratum exhausted. The terminal
classification is `CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED`.

The guard completed for 1,592 samples, with peak RSS 3,631 MiB against the
8,192 MiB cap and lowest available memory 19,460 MiB against the 8,192 MiB
floor; it reported no sample error or tripwire and released the lease. The
aggregate memory budget was 16,384 MiB. The result used only attempt-4 rows;
the prior attempt-3 rows and its 385 cross-schema exclusions were not reused.
No N>2 execution, convergence, training, promotion, native modification, or
automatic follow-on replay was performed.

## Corrected attempt 4 retained artifacts

Paths are under the ignored artifact root
`artifacts/t112-sampler-seed-contract-repair-76d2ff7`:

| Artifact | Schema | SHA-256 |
| --- | --- | --- |
| Input qualification `preparation-attempt-5/t112-input-qualification.json` | `t112-input-qualification-v1` | `8497abafdcabdedd00d84fcbc8bce1de5d616d7d90385554e902d74398436fca` |
| Readiness `preparation-attempt-5/t112-readiness-preparation.json` | `t112-readiness-preparation-v1` | `000c795b497ebb798702a24cbf4ff1340f0e7e9b6b27ee48462275052124690e` |
| Preparation retention manifest `preparation-attempt-5/t112-preparation-retention-manifest.json` | `t112-preparation-retention-manifest-v1` | `cf1a3ba06f83933abf9cf11b05b63bb27532eb9b8200ae67689c887759c4bcaf` |
| Witness terminal `witness-attempt-5/t112-witness-terminal.json` | `t112-native-witness-terminal-v2` | `62cf5100dd787e582fe989b42e2961ff74c33b44a16bea3b5adffad1a46eb3a0` |
| Cohort authorization `jobs/t112-cohort-authorization-accf76e-attempt-4.json` | `t112-maintainer-stage-authorization-v1` | `695a013899a4060ec4549bf9797db14cbfad8583cc00e77c09443f30814db3cd` |
| Detached resource status `jobs/t112-cohort-attempt-4.status.json` | `stsrl-detached-job-status-v1` | `42c3fc2ff977e038964a4d5eb8bb3a430213e17d4a2bb90ac6a9877c7d273800` |
| Candidate attempts `cohort-attempt-4/t112-candidate-attempts.jsonl` | `t112-candidate-attempts-jsonl-v2` | `22127da03747055184d7aa021435095b8d25784f473e9f671d77fb0682190418` |
| Cohort admission `cohort-attempt-4/t112-cohort-admission.json` | `t112-configured-search-cohort-admission-v2` | `3f83ab718bdcba98cdf26cc29233178fde96c7b9a796237139db499b34936ac1` |
| Execution record `cohort-attempt-4/t112-execution-record.json` | `t112-cohort-execution-record-v2` | `a3bd662e56c632a09cf8f3101f09a409437f511584195e3920cdb02c0e6af4e4` |
| Final report `cohort-attempt-4/t112-final-report.json` | `t112-final-report-v2` | `d14b67a1f3f76461cb2a356e52df2199c901d09b23c97f80379ac5293bf6b4c9` |
| Terminal retention manifest `cohort-attempt-4/t112-terminal-retention-manifest.json` | `t112-terminal-retention-manifest-v1` | `cd23575eec8f3ce8d95981534312adf7f05cccb3f6cf4ceb9391c5541b1980fb` |

The terminal manifest binds the detached status, native source manifest and
binary, preparation and witness outputs, T101/T111 predecessor records, and
T112 cohort artifacts by schema, size, and SHA-256. Large upstream inputs
remain outside Git.
