# T103 retained execution evidence

This is the factual result record for the
[T103 contract](../../T103-particle-search-support-domain-failure-taxonomy.md).
It describes the frozen support census, not a successor experiment or native
repair. The original unqualified run remains in the
[historical audit](../../../history/T103-first-diagnostic-audit.md).

## Execution identity and reproducibility

The scientific artifact producer is STSRL
`ec58e2ad396c149988ca639fd3b22244d331b9d7`, containing the independently
reviewed diagnostic repair `6662945d339000728208b6be7a8342a617cea575`.
The specification was approved at
`8b5e128dd6c5624f8f1cf7ac18fcd320ddad4401`; publication base and refreshed
remote `main` both resolve to
`56259175e5616ff334c6b74fa4e70d141df26783`.
Later factual landing-record commits do not rewrite this producer identity.

The exact T101-ordered population comprises 413 unique candidates, A/B/C
93/192/128. Each was attempted exactly once, retaining its original stratum,
source ordinal and selection digest. Replicate-0 seeds take the first eight
bytes of `SHA256(UTF8("T101-v1") || UTF8(selection_identity) || ASCII("0"))`
as an unsigned big-endian integer. Every call uses two particles, unguided
Search v2 at 400 simulations, and no potions. Selection is value/outcome blind.

The native consumer remains `lsmfttb/sts_lightspeed`,
`refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`.
Runtime is CPython 3.13.13 at
`/home/lsmft/stsrl-spikes/py313-torch/bin/python`, with module
`/home/lsmft/stsrl-spikes/build-t101-native-97f59b6-py313/slaythespire.cpython-313-x86_64-linux-gnu.so`,
SHA-256 `9eadacf39374d0fe64f407e0b93bbff14764926fcd30c965b7952e44bf64d42e`.

Historical B/C producers remain
`d62ff35579b54d70a7428afdf84743c94df3fe0c`, not the current consumer.
Their source manifests remain complete, frozen and outcome independent; their
pool paths, schemas, sizes and hashes match the retained T101 bindings.
B/C source-manifest hashes are respectively
`11b7a55cc1bca52481699c6ebe10f16af2ad1cdf1765b565fdfdbfe5aad93e06` and
`2a9986972764197d0c9b4927617c15a71221358364823d3f0f9687433face376`.
The deleted T101 worktree's native-manifest path remains historical provenance;
the current manifest supplies identical bytes at SHA-256
`a2b83373a0051a52a1e6092fe36fabab0e4478f98753c169580ae4b53c588205`.
No historical identity or path was rewritten.

## Census and evidence boundary

Terminal: `SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED`.
Zero admitted candidates reproduce the T101 support result.

| Observable first-failing class | A / 93 | B / 192 | C / 128 | Total / 413 |
| --- | ---: | ---: | ---: | ---: |
| `PUBLIC_PROJECTION_PARITY_FAILURE` | 4 | 3 | 63 | 70 |
| `OPAQUE_BRIDGE_FAILURE` | 89 | 189 | 65 | 343 |
| `ADMITTED` | 0 | 0 | 0 | 0 |

All other top-level classes have count zero. All 413 candidates restored and
passed the full pre-bridge public-context/action parity boundary, including
the shared projection-candidate guard and completeness metadata.
Seventy bridge calls returned reports whose projection parity failed; mapping
was complete and Search was directly observed as reached in those reports.
For the 343 failed bridge calls, mapping, Search and finite-root-report stages
remain `unknown`: the current surface does not justify a narrower class.
No candidate established a valid finite required root report. Two of the 70
returned reports additionally exposed invalid required values, but projection
parity was the earlier failing observable boundary and controls their class.

Exact exception type/signature counts are:

- `RuntimeError:1b66b7999a13e57f69f302bf9b80a4a6f280221ff56d0366ea08eefda7f84227`: 323/413;
- `T101IncompleteError:ce8d42e25e63e16dbbbb07b00d83a30288cbea6ca62f19e0f5123102fe6019bf`: 70/413;
- `RuntimeError:f50ca580caee3a938962e231a0fd25cd3d5b4ea7dcd74b7471a838f532179728`: 20/413.

Exception prose is not a causal classifier. Zero classified mapping failures
does not establish that mapping always works. The earlier three-sample mapping
diagnosis is not generalized to the remaining population. T103 establishes
neither hidden root cause, convergence, posterior correctness, controller
quality nor support outside these 413 records. T034 is not closed; T063/T066
remain non-active. No native repair or successor execution follows from this
result alone.

## Runtime and resources

The job started at `2026-09-27T05:12:29.267208Z` and finished at
`2026-09-27T09:09:45.350795Z`, with `SUCCEEDED`, exit code 0 and empty stderr.
Wall time was 14,236.083587 seconds (3 h 57 min 16 s): input qualification and
loading took 1,188.365165 seconds, replay 13,039.235221 seconds, and summed
candidate time 13,039.207076 seconds.

Host worker target 16; effective workers/shards 1, record positions `[0, 413)`.
The pinned pybind bridge holds the GIL; threads serialize native calls. No
resource-safe process-sharing path for the approximately 7.5 GB canonical B
pool is established. This tooling/memory limitation is the explicit reason
for one worker, not a small-smoke exemption.

The job reserved 5,120 MiB within a 6,144 MiB admission budget, with a 5,120 MiB
process-group RSS limit, 8,192 MiB MemAvailable floor and one-second guard
sampling. Observed peak RSS was 3,626 MiB and minimum MemAvailable 17,704 MiB.
No tripwire fired; the lease was released and both recorded processes were
absent at terminal inspection.

## Retained artifacts and regeneration

Stable ignored root outside disposable worktrees:
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t103-particle-search-support-domain-diagnostic-ec58e2a/`.

| File | Current schema | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `t103-candidate-diagnostics.json` | `t103-particle-support-diagnostics-v1` | 2752231 | `e9706fc1fd89c8e511931a79622b89753d29a342746601fdc93e8b8d1932f2ea` |
| `t103-aggregate-report.json` | `t103-particle-support-report-v1` | 12189 | `12d05289c30061c605e4b81a213423ae33a77095c330708d230d63a4a811c782` |
| `t103-retention-manifest.json` | `t103-diagnostic-retention-manifest-v1` | 9227 | `614cd617e91036e1eaf8126b4930cc1bdc364d43ef1337c7db5b01ca05d5ffcf` |

The sibling `jobs/t103-diagnostic.status.json` retains the complete command
argument array, working directory, process identities, resource settings and
terminal state. Its stdout log records the emitted result; stderr is empty.
The retention manifest binds both scientific outputs, original T101/source
references, producer identity, regeneration command and deletion condition.

Regenerate from the producer commit with the pinned runtime/module above,
using the status-file command array. Its explicit `PYTHONPATH` includes both
the native build directory and producer checkout's `src`. If the checkout
moves, adjust only those code/cwd bindings and choose a unique new output root;
never overwrite retained evidence. Maintainer owns retention for T103 audit
and successor planning; raw outputs may be deleted only after those consumers
close. The original 6104b94 run remains audit-only. Its classifications were
not reused: all affected candidates were replayed after repair. The new rows
match the original rows in every non-timing field, but final evidence is bound
to this repaired producer and these new hashes.

## Independent verification

Maintainer independently checked all output schemas, hashes and sizes, streamed
all 17 inherited artifact hashes, and verified B/C manifests and native binary.
Independent calculations, without production seed or aggregation helpers,
checked all identities/order/strata/ordinals/digests, frozen seeds/parameters,
row stage consistency, class/subreason/signature fractions and per-stratum
aggregates. Bounded real shared-builder tests establish pre-bridge rejection
for candidate/completeness mismatch and unchanged matching-call behavior.
Focused T103/T101/T099/public-context/task-doc tests: 99 passed.

Compileall, changed-file Ruff check/format, documentation guards/links and diff
checks pass. The full-suite regression check reports 1,494 passed, 12 failed;
the same 12 failures were reproduced on unchanged main. Ruff 0.16.5 reports
the same 528 inherited diagnostics and 24 formatting files on main and the
task branch, with no new diagnostic. These baseline limitations are reported,
not described as an all-green repository or repaired by widening T103 scope.
