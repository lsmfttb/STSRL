# T108 implementation and execution handoff

This file records the implemented workflow and the independently verified
T108 full-census execution. The terminal result is a bounded mapping-control-
flow subreason census for the exact accepted 323-row T106 root-mapping subset;
it is not a mechanics-root-cause or repair-efficacy result.

## Read-only input qualification

The command
`python -m sts_combat_rl.commands.t108_mapping_subreasons`
provides `--qualify-t106-inputs-only`. It verifies the exact accepted T106
rows, report, execution record, and retention-manifest hashes and provenance,
then filters the ordered T106 rows to 323
`ROOT_OCCURRENCE_MAPPING_FAILURE` identities. It also verifies the current
canonical source manifest and the T107 source-acceptance evidence. This mode
does not import or invoke the native simulator.

Against the primary checkout's retained T106 root, pass:

```text
--t106-rows <T106 root>/t106-candidate-stages.json
--t106-report <T106 root>/t106-aggregate-report.json
--t106-execution <T106 root>/t106-execution-record.json
--t106-manifest <T106 root>/t106-retention-manifest.json
```

The accepted input identities are pinned in the T108 task contract. The
read-only qualification output reports the T106 hashes, selected A/B/C counts,
and a digest of the exact ordered identity/source-ordinal/selection-digest
sequence without printing the identity list.

The read-only qualification completed on 2026-10-01. It accepted T106 producer
`1514f8ffd16f12c7d554a484be233d7e9c15e1bf`, selected 323 identities with
A/B/C counts `84/174/65`, and produced ordered identity digest
`fa798b1af6f88e542a09527703f89eb81310c882377938be2ed10056ec05cb38`. The four
input SHA-256 values were rows
`54475603f5072b316a4afc2b4e6ddb88b8ad2db0950c8ef3792347a07bbaae78`, report
`871771bcd94b558f7e85034ac95dd1f2b38da7550962bce71560ec9e8b9d015e`, execution
record `2093eee53ed28de8d6d5941c72fc4a90af4f961add1a1c78903b1d6b107ed4e4`, and
manifest `27141e5d6167da7c0fe5c62b8c6c673c5a02f5187bd9c8ae866dfd1443998647`.
The current native source pin qualified as
`1458522294d967e8985e1fd52cc15d7ebe7f2acd`. The command reported
`simulator_started: false`; it created no T108 scientific rows or terminal.

## Preserved bounded-canary attempts

Canary attempts 1 through 4 are preserved under
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t108-root-occurrence-mapping-subreason-diagnostic-41a789a/jobs/`.
Attempts 1, 2, and 3 failed before replay with exit code 2 and terminal
`INCOMPLETE`; they produced no T108 scientific rows and are non-authoritative.
Attempt 1 failed at the WSL worktree readiness check. Attempt 2 exposed the
T101 manifest resolver mismatch: accepted T106 provenance stores
`t101_terminal_retention_manifest` under `historical_t101_bindings`, not inside
`accepted_t101_source_artifacts`. Attempt 3 passed input hash validation but
was invoked with the detached T106 status JSON instead of the immutable T106
execution-record artifact, so the CLI rejected its hash before replay. The
resolver repair and each invocation failure are preserved; none of these
attempts may be overwritten or combined with another attempt.

Canary attempt 4 completed its limited plumbing, baseline-reproduction,
diagnostic-decoding, and resource checks. It selected only the 12 authorized
positions `[10,31,52,73,105,149,192,236,266,282,298,314]`, produced 12 valid
rows, and correctly terminated `INCOMPLETE` because it was a non-authoritative
subset. Its rows, report, execution record, and retention manifest remain
separate from the full census and are not combined with it.

For replay, T101, T103, T085, and T087 paths are resolved from the accepted
T106 retention manifest's transitive producer bindings. Existing T101/T103/
T087/T085 admission code then revalidates the selected source artifacts and
restore maps. This keeps replay inputs bound to the accepted T106 lineage.

## Completed full census

Full-census attempt 1 failed before simulator execution because its `PYTHONPATH`
omitted the verified native build directory. It produced no candidate rows,
report, execution record, or retention manifest and is preserved as an
operational failure only. It is not scientific evidence and was not combined
with attempt 2.

Full-census attempt 2 completed successfully at the unchanged implementation
head `dc7e6c53539552464dd501965f60520b9b5dd9bb` and terminal
`ROOT_OCCURRENCE_MAPPING_SUBREASON_CENSUS_ESTABLISHED`. The exact 323 accepted
T106 `ROOT_OCCURRENCE_MAPPING_FAILURE` identities were replayed in T106/T101
order (A/B/C `84/174/65`), with identity-order digest
`fa798b1af6f88e542a09527703f89eb81310c882377938be2ed10056ec05cb38`. No T106
public-fidelity or T104 Part-A rows were included. Every row reproduced the
T106 parent failure at `root_occurrence_mapping`, code
`root_occurrence_mapping_failed`, first failing particle 0; there were zero
baseline contradictions and zero parent/mapping telemetry-contract violations.
All 323 valid structured T107 diagnostics reported
`missing_non_card_direct_search_root_match`; all six other accepted failure
subreasons had count 0, and the seven categories sum exactly to 323. This
classifies an observed native mapping-control-flow branch only. It does not
establish a mechanics cause, a native or STSRL repair, or repair efficacy.

The replay retained replicate 0 and accepted T101-derived seeds,
`particle_start=0`, N=2, unguided Search-v2@400, `include_potions=false`, and no
failure injection. It used native source commit
`1458522294d967e8985e1fd52cc15d7ebe7f2acd` and binary SHA-256
`e573ba6978fd28f43fa2bfbbe292f6891df3cbb916d9496cf02d7dbb8ceed855`. Four
fork workers (PIDs 541–544) processed ranges `[0,81)`, `[81,162)`, `[162,243)`,
and `[243,323)`. Wall time was 79m55s (input qualification 1,077.98s; replay
3,711.60s). The 4,788-sample resource guard recorded peak summed RSS
12,767 MiB under the 16,384 MiB cap and minimum `MemAvailable` 17,389 MiB above
the 8,192 MiB floor, with no sampling error or tripwire; the lease was released
normally.

The retained output root is
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t108-root-occurrence-mapping-subreason-diagnostic-41a789a/full-323-attempt-2/`:

| Artifact | Schema | SHA-256 |
|---|---|---|
| `t108-candidate-mapping-subreasons.json` | `t108-root-mapping-subreason-rows-v1` | `bbd8db3dafcfcb729f198b1f5c7c86d6d1156ef0041ed74e8d00965e0a1f8c26` |
| `t108-aggregate-report.json` | `t108-root-mapping-subreason-report-v1` | `df61a122d7d01d9aa89fccfefe578c09e0c304a2841887146aedf67af5c2bbd6` |
| `t108-execution-record.json` | `t108-execution-record-v1` | `8faf47cf79807bde3ef70182ad798ecb27a6d670cf2ae8dc70a2fbce1b7a64fb` |
| `t108-retention-manifest.json` | `t108-root-mapping-subreason-retention-manifest-v1` | `35f8e53f75f98134922a7725d25986696678f102ff1808000c2e81fc934fa8e2` |

The exact-head full-readiness authorization is
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t108-root-occurrence-mapping-subreason-diagnostic-41a789a/jobs/t108-full-readiness-dc7e6c5-attempt-2.json`, SHA-256
`d3874fa7ff54270ed92c1ae39aa4338216307ffe74fdc0d1c87471e7626952da`; it cites
Maintainer authorization in PR comment
[5920654306](https://github.com/lsmfttb/STSRL/pull/126#issuecomment-5920654306)
and the corrected resource-root note in comment
[5920661952](https://github.com/lsmfttb/STSRL/pull/126#issuecomment-5920661952).
The independent terminal audit and full retained-path hash review are recorded
in [the Maintainer full-census follow-up](https://github.com/lsmfttb/STSRL/pull/126#issuecomment-5922040727).

Attempt directories are immutable and remain separate: failed full attempt 1,
successful full attempt 2, and non-authoritative canary attempt 4. No partial or
canary rows were merged into the 323-row terminal census. Do not infer a cause,
propose a repair, replay the separate 20 public-fidelity rows or 70 Part-A rows,
change the frozen settings, run N>2/convergence/training, or promote a
controller from this result.
