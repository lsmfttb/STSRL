# T103 retained execution evidence

This is the factual execution record for
[T103](../tasks/T103-particle-search-support-domain-failure-taxonomy.md).
The scientific contract and its terminal meanings remain owned by that task.

This original run is retained for audit only and is not accepted final evidence.
Maintainer re-review found that the diagnostic context construction bypassed
the shared T101 native-projection/action parity guard and omitted completeness
metadata from comparison. The counts below describe the original output, not
an accepted first-failing-boundary taxonomy. Repair review and replay of the
affected boundary onward are required before a final result can be recorded.

The instrumentation repair was independently reviewed at
`6662945d339000728208b6be7a8342a617cea575`. It restores the existing shared
candidate-parity guard, uses the full projected context, and retains
`missing_fields`; it does not change the shared helper, native identity or
bridge configuration. Original classifications below cannot be reused across
this affected pre-bridge boundary. Source qualification remains reusable only
with the original retained identities verified; the new execution revalidates
those inputs and writes a distinct output root.

## Producer and inputs

The STSRL implementation producer is
`6104b940d4466ac7a29f15282583d69aa9cff5d4`, under the specification approved at
`8b5e128dd6c5624f8f1cf7ac18fcd320ddad4401`. The synchronized publication base
and refreshed remote `main` were both
`56259175e5616ff334c6b74fa4e70d141df26783`.

Execution consumed the exact T101-ordered 413-record population, with A/B/C
counts 93/192/128. Each selection identity retained its original stratum,
ordinal, selection digest, and replicate-0 seed derived from
`SHA256(UTF8("T101-v1") || UTF8(selection_identity) || ASCII("0"))`, taking
the first eight bytes as an unsigned big-endian integer. Each candidate was
attempted once with two particles, 400 Search-v2 simulations, and no potions.
No candidate was chosen or skipped using values, rankings, outcomes, or hidden
diversity.

The current native consumer is `lsmfttb/sts_lightspeed`,
`refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`.
Runtime was CPython 3.13.13 with native module
`/home/lsmft/stsrl-spikes/build-t101-native-97f59b6-py313/slaythespire.cpython-313-x86_64-linux-gnu.so`,
SHA-256 `9eadacf39374d0fe64f407e0b93bbff14764926fcd30c965b7952e44bf64d42e`.

Historical B/C source manifests retain their actual native producer
`d62ff35579b54d70a7428afdf84743c94df3fe0c`; this is distinct from the current
consumer. Their pool hashes match the retained T101 bindings. The old T101
worktree's native-manifest path is historical provenance, not a required live
worktree: the current manifest has the exact retained SHA-256
`a2b83373a0051a52a1e6092fe36fabab0e4478f98753c169580ae4b53c588205`.
No historical producer identity was rewritten.

## Observed result

Original emitted terminal: `SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`.
The output reports zero admission; its classification validity is not accepted.
The exact original emitted census is:

| Observable first-failing class | A / 93 | B / 192 | C / 128 | Total / 413 |
| --- | ---: | ---: | ---: | ---: |
| `PUBLIC_PROJECTION_PARITY_FAILURE` | 4 | 3 | 63 | 70 |
| `OPAQUE_BRIDGE_FAILURE` | 89 | 189 | 65 | 343 |
| `ADMITTED` | 0 | 0 | 0 | 0 |

Every other task-defined class has count zero. All 413 rows report successful
restore and matched context/actions, but the omitted shared guard means this
does not establish full T101 pre-bridge equivalence. Seventy calls returned a report with directly observed
public-projection parity failure during bridge-report checking; those reports
established that mapping and Search were reached. The remaining 343 calls
failed without sufficient structured stage information to localize the native
boundary; their mapping, Search, and valid-root-report statuses remain
`unknown`. No candidate reached a fully validated finite required root report.

The retained exact exception type/signature counts are:

- `RuntimeError:1b66b7999a13e57f69f302bf9b80a4a6f280221ff56d0366ea08eefda7f84227`: 323;
- `RuntimeError:f50ca580caee3a938962e231a0fd25cd3d5b4ea7dcd74b7471a838f532179728`: 20;
- `T101IncompleteError:ce8d42e25e63e16dbbbb07b00d83a30288cbea6ca62f19e0f5123102fe6019bf`: 70.

Exception prose/signatures were not used to invent a scientific cause. Zero
classified occurrence-mapping failures means that this execution did not
establish that class; it does not establish that native mapping always works.
The result does not identify every hidden root cause or justify applying the
earlier three-candidate occurrence-mapping observation to the full population.

## Runtime and resource evidence

The detached job started at `2026-09-26T19:03:10.506270Z` and finished at
`2026-09-26T23:11:39.501736Z`, with `SUCCEEDED`, exit code 0, and empty stderr.
Wall time was 14,908.995466 seconds (4 h 8 min 29 s), including
1,426.267088 seconds loading/qualifying inputs and 13,476.540418 seconds of
replay. Summed per-candidate time was 13,476.509780 seconds.

The host worker target was 16; effective workers and shards were both 1, with
the full record-position range `[0, 413)`. The pinned pybind bridge holds the
GIL, so threads would serialize native calls. A safe process-sharing path for
the approximately 7.5 GB canonical B pool was not established. This tooling
and memory limitation is the recorded reason for single-worker execution;
neither native code nor the scientific configuration was changed.

The resource lease requested 5,120 MiB within a 6,144 MiB admission budget.
The runtime guard recorded peak process-group RSS 3,626 MiB and minimum host
MemAvailable 15,198 MiB, above the 8,192 MiB floor. No tripwire fired. The
lease was released, and the supervisor/child processes were absent at terminal
inspection.

## Retained outputs and regeneration

Stable ignored retention root:
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t103-particle-search-support-domain-diagnostic-6104b94/`.

| File | Current schema | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `t103-candidate-diagnostics.json` | `t103-particle-support-diagnostics-v1` | 2752260 | `19f3f45c002c1905aef86865753e9665e2be531e966a6462f1e8b23bb4478dd8` |
| `t103-aggregate-report.json` | `t103-particle-support-report-v1` | 12192 | `66c24ff555d6cd4b3430428047f5502e44d9ed1d3566a4b7d203c8722e793a6a` |
| `t103-retention-manifest.json` | `t103-diagnostic-retention-manifest-v1` | 9227 | `0e6c11656e49ad672243ea668976ece5eb08b074a74ba2d789852e422623cd15` |

Under this root, `jobs/t103-diagnostic.status.json` retains the complete
command argument array, working directory, process identities, resource
configuration, and terminal status. Its sibling `.stdout.log` records the
complete emitted result, and `.stderr.log` is empty. The retention manifest
binds the two scientific outputs and all inherited T101 source references.

To regenerate, check out the STSRL producer commit, use the pinned native
module and CPython runtime above, and execute the recorded status-file command
array. Its `PYTHONPATH` contains both that native build directory and the
producer checkout's `src` directory. If the checkout moves, change only its
code path and working directory. Select a new unique output directory: the
writer intentionally refuses to overwrite the retained originals. The
manifest's module command inherits this explicit runtime/environment setup;
the status-file command is the complete launcher reference.

Retain these outputs for T103 audit and successor planning. Raw diagnostics
may be deleted only after all those consumers close. T103 authorizes no native
repair, N>2 run, convergence experiment, training, or controller promotion.

## Independent evidence verification

Maintainer independently parsed all output schemas and verified their byte
lengths and hashes. Every inherited T101 artifact/source binding was streamed
and checked against its retained byte length and SHA-256; the identical current
native manifest supplies the historical manifest bytes described above.
The B/C source manifests preserve the distinct historical producer identity.

Independent calculations, without calling the production aggregate or seed
helpers, verified all 413 unique identities, exact T101 attempt order,
strata/ordinals/digests, replicate-0 seeds, frozen parameters, current native
identity, row status consistency, exact class and signature counts, integer
fractions, and per-stratum sums. All scientific outputs remain unchanged after
verification. Repository review/check evidence is recorded on PR #119.
