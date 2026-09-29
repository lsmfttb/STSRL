# T106 retained structured failure-stage census

This is the factual execution record for the
[T106 contract](../../T106-structured-particle-search-failure-stage-reentry.md).
It records the bounded scientific result and operational evidence, not a live
PR approval phase.

## Result and scientific boundary

Terminal: `PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED`.

The full execution replayed exactly the accepted 343 T104 Part-B identities in
T101/T104 order. Every candidate reproduced its previously accepted failed
full-bridge outcome and yielded a valid immediate
`native-particle-search-stage-observability-v1` trace. Baseline contradictions
were 0; telemetry-contract violations were 0. Historical T104 Part-B classes
remain 323 `BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS` and 20
`STANDALONE_SAMPLER_FAILURE`; A/B/C counts remain 89/189/65.

| T106 first-failed control-flow class | Total / 343 | A / 89 | B / 189 | C / 65 |
| --- | ---: | ---: | ---: | ---: |
| `ROOT_OCCURRENCE_MAPPING_FAILURE` | 323 | 84 | 174 | 65 |
| `PUBLIC_FIDELITY_VALIDATION_FAILURE` | 20 | 5 | 15 | 0 |
| `REQUEST_OR_PREFLIGHT_FAILURE` | 0 | 0 | 0 | 0 |
| `HIDDEN_FUTURE_SAMPLE_CONSTRUCTION_FAILURE` | 0 | 0 | 0 | 0 |
| `SEARCH_SETUP_FAILURE` | 0 | 0 | 0 | 0 |
| `SEARCH_EXECUTION_FAILURE` | 0 | 0 | 0 | 0 |
| `SANITIZED_ROOT_REPORT_FAILURE` | 0 | 0 | 0 | 0 |

All 323 historical standalone-sampler-success rows first failed at
`root_occurrence_mapping` with structured code
`root_occurrence_mapping_failed`. All 20 historical standalone-sampler-failure
rows first failed at `public_fidelity_validation` with structured code
`anchor_unsupported_fidelity`. These historical labels are cross-tabulated
only; they do not define the monolithic stage. First failing particle index is
0 for the 323 root-mapping cases. It is unavailable for the 20 public-fidelity
cases because failure preceded particle-stage execution. The report retains
all seven classes, structured failure-code cross-tabs, stage-transition
signatures, and exact integer fractions.

This localizes only the first failed native control-flow stage. It does not
identify a mechanics root cause inside that stage or establish repair efficacy,
support improvement, N>2 sufficiency/convergence, controller quality, or a
population claim beyond the frozen 343 identities. No Part-A replay, native
source change, mechanics repair, N>2 execution, training, or controller
promotion occurred.

## Frozen configuration and producer lineage

The T106 scientific execution producer and exact reviewed implementation head
are `1514f8ffd16f12c7d554a484be233d7e9c15e1bf`. The approved specification
commit is `857a24b0b38938fc8c0144f8ea36daefd9a5031a`. Full-readiness approval
was bound to that exact head and attempt 2; its JSON is retained at
`artifacts/t106-structured-particle-search-failure-stage-ca4f612/jobs/t106-full-readiness-authorization-1514f8f-attempt-2.json`
with SHA-256
`311fe12de1705b4eec8a0468b03258e15716cc52ac948ba656d04ab9549cd4f8`.

Accepted predecessor identities remain distinct:

- T104 scientific producer: `90cbe6c5020f2fb360503e7731c9a892afc6447a`.
- T103 repaired producer: `ec58e2ad396c149988ca639fd3b22244d331b9d7`.
- T101 retained execution head: `361a77dbe88b2215a92cfe96e4f4c5c243f7ff1c`.
- Historical T101/T103/T104 native identity:
  `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 97f59b620efe5ee1571f8da298c99d1e21c1149b`.
- Current T105-accepted native identity:
  `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 5afae22def0c69657b0139bfa21306aebac831af`.
- Runtime binary:
  `/home/lsmft/stsrl-spikes/build-t106-native-5afae22-py313/slaythespire.cpython-313-x86_64-linux-gnu.so`,
  SHA-256 `5c30a764470e71b3e7b75e97aaecfd6d51b5c1dc9feaf3455140108069ec4019`.
- Historical B/C source producer remains
  `d62ff35579b54d70a7428afdf84743c94df3fe0c`.

The qualified upstream terminal references are bound by the T106 retention
manifest and independently rehashed before the replay:

| Input evidence | Producer / schema | SHA-256 |
| --- | --- | --- |
| T104 candidate rows | `90cbe6c`; `t104-bridge-localization-rows-v1` | `3232719325d790dcc84f7e91f907d12b56da37c7557edc8848a5f38fe530dd41` |
| T104 aggregate report | `90cbe6c`; `t104-bridge-localization-report-v1` | `d59e5c9c09dd780a522b018be045dc0656d1e0fe4f78f6406a204684a54ef0ff` |
| T104 retention manifest | `90cbe6c`; `t104-localization-retention-manifest-v1` | `e1d380177f3f68484809b6bac99f7d3477c3ad29e16229f08e70aa46d52da7ba` |
| T104 attempt-2 execution status | `90cbe6c` | `b3d1e3d4b0e0e753614c0d38eecb8b35e05a844ea09559f5d3bc3b4413df5295` |
| T103 candidate diagnostics | `ec58e2a`; `t103-particle-support-diagnostics-v1` | `e9706fc1fd89c8e511931a79622b89753d29a342746601fdc93e8b8d1932f2ea` |
| T103 aggregate report | `ec58e2a`; `t103-particle-support-report-v1` | `12d05289c30061c605e4b81a213423ae33a77095c330708d230d63a4a811c782` |
| T103 retention manifest | `ec58e2a`; `t103-diagnostic-retention-manifest-v1` | `614cd617e91036e1eaf8126b4930cc1bdc364d43ef1337c7db5b01ca05d5ffcf` |
| T103 execution status | `ec58e2a` | `171e04a7271707513ae7310a71c9419cf08df3de3490c338610e97a387170d08` |
| T101 terminal retention manifest | `361a77d`; `t101-terminal-retention-manifest-v1` | `922ef003d2fa15dea57f59c71fa99bfb6f5a418d48026b04ed3019d7e6cf4f97` |

Every selected row preserves its T101-derived replicate-0 seed,
`particle_start=0`, `particle_count=2`, unguided Search v2 at 400 simulations,
and `include_potions=false`. Each bridge replay used a fresh restored adapter;
the T105 trace was read immediately after the corresponding production bridge
call. Classification comes only from the validated structured trace, never
exception prose.

## Execution, workers, and resource guard

Full census attempt 2 ran from `2026-09-29T11:24:37.719594Z` to
`2026-09-29T14:23:48.656952Z`, succeeded with exit code 0, and took
10,750.94 seconds (about 2 h 59 min 11 s). Input qualification/loading took
1,396.233 seconds and replay took 9,332.478 seconds. The runtime used four
Linux fork workers; native calls retain the GIL. Worker target was 16, reduced
to four under the reviewed resource plan after T104's six-worker summed-RSS
guard trip.

| Worker PID | T101/T104-order range | Records |
| --- | --- | ---: |
| 1831 | `[0,86)` | 86 |
| 1832 | `[86,172)` | 86 |
| 1833 | `[172,258)` | 86 |
| 1834 | `[258,343)` | 85 |

The unchanged detached guard reserved and capped summed RSS at 16,384 MiB,
kept the MemAvailable floor at 8,192 MiB, and sampled once per second. It
completed 10,716 samples with peak summed RSS 13,911 MiB, minimum MemAvailable
16,531 MiB, no sample error, and no tripwire. The lease was released. The
terminal status records supervisor/target PIDs 509/510 and the complete
worker/shard/wall/resource evidence.

Attempt 1 remains preserved as a guard-observation failure: the monitor could
not read a process `VmRSS` field, although recorded RSS/MemAvailable were
within thresholds. It produced no scientific outputs and is not census
evidence. Canary attempt 1 was terminated before output because its command
contained invalid C-source paths and is also not scientific evidence. The
successful bounded canary attempt 2 and full census attempt 2 are the retained
scientific executions; canary evidence was not generalized beyond its sample.

## Retained artifacts and regeneration

Stable ignored retention root outside disposable worktrees:
`artifacts/t106-structured-particle-search-failure-stage-ca4f612/` in the
primary STSRL checkout. The accepted full output is specifically
`full-343-attempt-2/`.

| Relative path | Schema | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `full-343-attempt-2/t106-candidate-stages.json` | `t106-structured-failure-stage-rows-v1` | 1,004,307 | `54475603f5072b316a4afc2b4e6ddb88b8ad2db0950c8ef3792347a07bbaae78` |
| `full-343-attempt-2/t106-aggregate-report.json` | `t106-structured-failure-stage-report-v1` | 11,904 | `871771bcd94b558f7e85034ac95dd1f2b38da7550962bce71560ec9e8b9d015e` |
| `full-343-attempt-2/t106-execution-record.json` | `t106-execution-record-v1` | 2,539 | `2093eee53ed28de8d6d5941c72fc4a90af4f961add1a1c78903b1d6b107ed4e4` |
| `full-343-attempt-2/t106-retention-manifest.json` | `t106-failure-stage-retention-manifest-v1` | 27,305 | `27141e5d6167da7c0fe5c62b8c6c673c5a02f5187bd9c8ae866dfd1443998647` |

Job status is retained at
`jobs/t106-full-census-attempt-2.status.json` (SHA-256
`cd0bc46c3b174bfb40be5b48a52eb5c0d7c2abc65f540c38c26386790bc90448`). Its
complete stdout is `jobs/t106-full-census-attempt-2.stdout.log` (SHA-256
`491d9d57d41bd610a1d7ce49353ebc993c95f5154b1a7397af719d9fef6b3db7`);
stderr is empty (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). The
status retains the full argument array and resource settings for regeneration.
The retention manifest binds schemas, sizes, hashes, producer/runtime
identities, input references, and the regeneration command. Never overwrite
these retained outputs; any authorized regeneration requires a new output
root. Raw evidence remains retained for T106 audit and successor observability
consumers and may be deleted only after those consumers close. No generated
binary or GB-scale input is committed.

One inherited T101 source-manifest reference names the pruned absolute path
`/mnt/d/DeadlyCatCoding/STSRL-T101/docs/sts_lightspeed_source_manifest.json`.
That path is unavailable, but the exact 16,886-byte blob was recovered from
T101 producer commit `361a77dbe88b2215a92cfe96e4f4c5c243f7ff1c` and matches
SHA-256 `a2b83373a0051a52a1e6092fe36fabab0e4478f98753c169580ae4b53c588205`
and schema `sts-lightspeed-source-manifest-v1`. The historical path was not
rewritten; its content and Git provenance were independently verified.

## Independent verification and limitations

Maintainer independently checked the current PR/worktree head and clean state;
the job status, exit code, logs, terminal processes, resource guard, artifact
schemas/sizes/hashes, and readiness binding; the accepted T104/T103/T101 joins
and all 343 ordered identities; historical and A/B/C counts; manually derived
replicate-0 seeds and frozen call parameters; current and historical native
identities; strict trace schema and stage/failure-code aggregates; worker PID,
shard, and resource evidence; and output/report parity. All 23 unique
referenced retained input artifacts were rehashed (10,101,800,273 bytes total),
including the T101 source-manifest Git blob noted above. No candidate admitted,
no baseline changed, and no trace violation was observed.

Repository-wide inherited test/lint/format limitations are not reclassified as
green by this diagnostic. This record makes no claim about the mechanics defect
inside either localized stage and authorizes no successor execution or repair.
