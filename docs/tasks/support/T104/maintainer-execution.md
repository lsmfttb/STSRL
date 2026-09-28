# T104 retained diagnostic execution

This is the factual execution record for the
[T104 contract](../../T104-particle-bridge-failure-localization.md).
It records the result contributed by this task, not a live PR approval phase.

## Result and scientific scope

Terminal: `NATIVE_OBSERVABILITY_REQUIRED`.

All 413 unique candidates reproduce the accepted T101/T103 order, source
ordinals/digests, replicate-0 seeds and T103 classes. A/B/C counts are
93/192/128; admissions remain 0/413. Every probe uses N=2,
`particle_start=0`, unguided Search v2 at 400 simulations and no potions.
Independent bridge and standalone sampler lanes restore fresh adapters; an
isolated sampler result does not establish a monolithic bridge stage.

| Evidence group | Total | A | B | C |
| --- | ---: | ---: | ---: | ---: |
| Part A: `PROJECTION_FAILURE_LOCALIZATION_OPAQUE` | 70 | 4 | 3 | 63 |
| Part B: `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` | 323 | 84 | 174 | 65 |
| Part B: `STANDALONE_SAMPLER_FAILURE` | 20 | 5 | 15 | 0 |
| Part B: native observability required | 343 | 89 | 189 | 65 |

All other Part A/Part B classes have count zero. Part B standalone public
fidelity failures are zero. The descriptive `NATIVE_STAGE_OPAQUE` class also
has count zero; it is **not** the observability gate. The independent predicate
is true for all 343 Part B rows, with no directly established monolithic repair
boundary. The 20 standalone failures do not supply structured facts identifying
the corresponding monolithic failure stage.

For all 70 Part A rows, comparable T096 `P0`, anchor and both particle public
payloads are equal, ordered public actions/duplicate occurrences are equal,
and structured public/action failure flags are false. No comparable field drift,
affected particle or action drift is established. The accepted T103 parity class
still reproduces against its separately retained T014 baseline representation:
all 70 retain one canonical 38-path missing/type/unequal signature. This is
representation-boundary evidence, not a claim of native public-state mutation
or a repair efficacy result. The existing public surfaces do not support a
narrower published Part A class, so explicit opacity is retained.

### Minimal future observability requirement

All 343 Part B rows retain `unknown` for the same six monolithic outcomes:

- hidden-future sample construction;
- public-fidelity validation;
- root occurrence mapping;
- Search setup;
- Search execution;
- sanitized root-report construction/validation.

The exact ordered stage names and aggregate fractions are retained in the
report. A future governed native task would need stable, non-secret
entered/completed/failed status for these boundaries to distinguish a repair
target. Exception text/signatures are audit grouping only. Neither successful
standalone sampling nor exception prose identifies the monolithic failed stage.
This record does not authorize native implementation, mechanics repair,
convergence, N>2, training, promotion, T034 closure or T063/T066 activation.

## Producer and retained artifacts

Scientific implementation producer:
`90cbe6c5020f2fb360503e7731c9a892afc6447a`.
The factual landing-record commit may differ; documentation-only changes do not
replace this producer or require rerunning unaffected native outputs.
Approved specification: `d0bc49c09548a91cca21b805cf0b0d58e58fff74`.
Publication/synchronized main base:
`72b96734c33b52687aa94e36b681d4c6648b054f`.

Accepted T103 producer: `ec58e2ad396c149988ca639fd3b22244d331b9d7`;
its manifest SHA-256 is
`614cd617e91036e1eaf8126b4930cc1bdc364d43ef1337c7db5b01ca05d5ffcf`.
Audit-only producer `6104b94` is not a scientific input. Current native:
`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`;
CPython 3.13.13 binary SHA-256:
`9eadacf39374d0fe64f407e0b93bbff14764926fcd30c965b7952e44bf64d42e`.
Historical B/C source producer remains distinct:
`d62ff35579b54d70a7428afdf84743c94df3fe0c`.

Stable ignored root outside the disposable review worktree:
`artifacts/t104-bridge-localization-90cbe6c/` in the primary STSRL checkout
(`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t104-bridge-localization-90cbe6c/`).
The accepted full output is specifically `full-attempt-2/`, not the canary or
failed first attempt.

| Relative path | Schema | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `full-attempt-2/t104-candidate-localization.json` | `t104-bridge-localization-rows-v1` | 6237910 | `3232719325d790dcc84f7e91f907d12b56da37c7557edc8848a5f38fe530dd41` |
| `full-attempt-2/t104-aggregate-report.json` | `t104-bridge-localization-report-v1` | 15998 | `d59e5c9c09dd780a522b018be045dc0656d1e0fe4f78f6406a204684a54ef0ff` |
| `full-attempt-2/t104-retention-manifest.json` | `t104-localization-retention-manifest-v1` | 19743 | `e1d380177f3f68484809b6bac99f7d3477c3ad29e16229f08e70aa46d52da7ba` |

Execution: `jobs/census-attempt-2.status.json`, SHA-256
`b3d1e3d4b0e0e753614c0d38eecb8b35e05a844ea09559f5d3bc3b4413df5295`;
complete stdout/stderr: `jobs/census-attempt-2.stdout.log` and
`jobs/census-attempt-2.stderr.log` (stderr empty).
The manifest binds exact input references, schemas/hashes/sizes, producer/runtime
identities and the complete argument-array regeneration command. Reproduce from
that scientific producer through the detached resource convention using a new
output root; do not overwrite retained evidence. The
[implementation binding](implementation-and-execution.md) describes the CLI.
Maintainer owns retention. Raw evidence is needed for T104 audit and successor
observability planning, not repair/convergence reuse; delete only after those
consumers close. No generated binary or GB-scale input is committed.

## Execution costs and resource calibration

The bounded 18-record canary used 16 workers and completed in 3357.06 seconds:
3136.01 input qualification plus 217.23 replay. Its aggregate RSS peak was
14740 MiB and minimum MemAvailable16987 MiB. It reproduced all 18 baselines with
complete diagnostic evidence; partial terminal `INCOMPLETE` reflects only the
395 omitted candidates. Its manifest SHA-256 is
`6d23effadaf87ec6a1faaffcb658cac307e5ad756becfddf584a7ebca85df0db`.
Those subset results were not generalized to the full population.

The initial six-worker full attempt ran from 2026-09-27 16:20:35 to16:37:26 UTC
(1011.03 seconds), then the unchanged summed-RSS guard terminated it at
20024 MiB against16384 MiB. Minimum MemAvailable17411 MiB, no observation error,
empty logs and no partial diagnostic output establish a resource-plan failure,
not OOM or a scientific baseline contradiction. Its status/logs remain under
`jobs/census.*`; its lease was released. Full restore-map footprint exceeded
the canary-derived projection. The guard includes parent and child VmRSS,
counting shared fork pages repeatedly; it was not replaced with PSS or relaxed.

The successful retry used four Linux fork processes, not threads; native retains
the GIL. Input qualification ran once in the parent; only selected immutable
restore maps survived before fork. Host target16 was reduced to4 because of the
measured six-worker guard failure. The unchanged reservation/RSS limit was
16384 MiB, MemAvailable floor8192 MiB and sample interval1 second.

| Worker PID | T101-order range | Records | Sum of record wall seconds | Per-worker peak RSS MiB |
| --- | --- | ---: | ---: | ---: |
| 62979 | [0,104) | 104 | 4600.875 | 2858.125 |
| 62980 | [104,207) | 103 | 11027.570 | 2858.000 |
| 62981 | [207,310) | 103 | 8294.054 | 2858.000 |
| 62982 | [310,413) | 103 | 464.955 | 2858.125 |

Attempt2 ran2026-09-27 17:27:59 to20:49:15 UTC, total12076.11 seconds
(3h21m16s): input qualification1045.30 seconds and process replay11027.87 seconds.
Supervisor62586/target62587 and all workers were absent at terminal verification.
Runtime guard completed12052 samples, peak group RSS14299 MiB and minimum
MemAvailable15091 MiB; no tripwire or observation error. Exit0, lease released.
The interim independent per-process RSS/PSS snapshot is retained under
`artifacts/t104-maintainer-tools/census-attempt-2-live-calibration-20260927T182338.json`;
PSS was explanatory only, not the admission metric. The initial five-hour ETA was
a conservative projection, superseded by these measured terminal costs.

## Independent verification and limitations

Maintainer independently checked all413 rows against T101 ordered attempts and
accepted T103 rows, manually derived seeds, native/historical producer bindings,
schemas/hashes/sizes, public-only projections, canonical38-path differences,
worker/PID/range bindings and all aggregate integer counts/fractions. The six
unknown monolithic stages and independent observability predicate yield343 true
and0 false; the terminal is not inferred from class8 coverage. Full stdout/report
parity and no surviving job process were checked. All17 retained T103 input
references were streamed/rehashed again, including large source pools and the
historical B/C manifests; the removed historical native-manifest path uses
identical verified bytes from the current checkout without rewriting lineage.

The independent checker is retained at
`artifacts/t104-maintainer-tools/verify-full-census-90cbe6c.py`; it invokes no
simulator or production classifier. Focused regression, documentation,
compile/lint/format and diff checks accompany the exact-head PR review.
Repository-wide inherited limitations remain12 test failures,528 Ruff diagnostics
and24 formatting files documented by T103; no all-green claim is made. The result
is bounded diagnosis, not a fully identified native defect or a controller result.
