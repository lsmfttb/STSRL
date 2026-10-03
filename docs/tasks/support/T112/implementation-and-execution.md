# T112 implementation and execution evidence

## Current lifecycle status

Stage-2 attempt 3 is preserved as execution evidence, but it is not a T112
scientific terminal. The exact-head Planner review in PR comment
[5964590261](https://github.com/lsmfttb/STSRL/pull/130#issuecomment-5964590261)
rejected its `CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT`
classification: the 385 `public_projection_parity_failure` rows compare two
different schemas, so they cannot establish a support-domain exclusion. The
current PR remains open and draft while the Planner-authorized narrow
T014/T096 parity correction and a fresh bounded re-entry are pending. The
attempt 3 report, rows, logs, and retention manifest remain immutable evidence
and must not be combined with or reclassified as rows from the corrected run.

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

The Maintainer reviewed the exact implementation head and recorded focused
verification: 140 T111/T099/T110/T112 tests, Ruff and formatting checks,
`compileall`, and `git diff --check` passed. No native source was modified.
The accepted native source pin is
`lsmfttb/sts_lightspeed@6496fc1c7e629a374b72bd94f7fd29afe29c7f62`; binary
SHA-256 is
`cdf650362a8178aed1919efb05b2255a8986562d6617e659e8e0dca26583dd3a`.

Stage-1 witness attempt 4 was finalized as
`N2_WITNESS_SEED_CONTRACT_ACCEPTED`: exactly one native bridge call, zero
retries, matching requested/observed `sampler_seed_input`, valid indexed
native-derived particle seed metadata, and no selector invocation. Its terminal
artifact is
`artifacts/t112-sampler-seed-contract-repair-76d2ff7/witness-attempt-4/t112-witness-terminal.json`
(SHA-256
`788b638169508afaaee570501a64f8864a8b51c27996d71b2fca6a6aaa1fc976`).

## Cohort execution

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

## Retained artifacts

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

The retention manifest binds the detached resource status, native source
manifest and binary, preparation and witness outputs, T101/T111 predecessor
records, and T112 cohort artifacts by schema, size, and SHA-256. The finalizer
validated these bindings; large upstream inputs remain outside Git.

No N>2 execution, convergence, training, promotion, native modification, or
automatic follow-on replay was performed. These artifacts preserve attempt 3
history only; T112 remains in progress until the corrected exact-head bounded
result and required Maintainer/Planner lifecycle reviews are complete.
