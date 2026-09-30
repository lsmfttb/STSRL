# T108 implementation and execution handoff

This file describes the implemented workflow and the later readiness boundary.
It is not T108 replay evidence. No T108 simulator replay has been run.

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

For replay, T101, T103, T085, and T087 paths are resolved from the accepted
T106 retention manifest's transitive producer bindings. Existing T101/T103/
T087/T085 admission code then revalidates the selected source artifacts and
restore maps. This keeps replay inputs bound to the accepted T106 lineage.

## Replay readiness proposal

T108 has no simulator authorization file yet. A Maintainer can review this
proposed full-population plan after implementation checks and a fresh exact-pin
native build are independently verified:

- four WSL/Linux fork workers, using T106's accepted four-worker calibration;
- contiguous T108-order shards `[0,81)`, `[81,162)`, `[162,243)`, and
  `[243,323)`;
- the existing detached resource guard with summed RSS capped at 16,384 MiB,
  minimum `MemAvailable` of 8,192 MiB, and one-second sampling;
- approximate elapsed time of 2 hours 50 minutes, estimated by scaling T106's
  measured 343-row replay and adding its input-loading time. This is a planning
  estimate; readiness should refresh it from any later bounded operational
  calibration.

Every replay scope, including a later bounded canary, requires a T108 readiness
JSON bound to the exact implementation head, exact positions, native binary
path/hash/source commit, worker count, and detached-guard status path. The
full-population readiness additionally requires
`full_population_authorized: true` and all 323 ordered positions. The approval
must cite a Maintainer comment on PR #126. The command will not start a replay
without that file and rejects a readiness record for another head, subset, or
binary.

The eventual full command uses the four T106 artifact paths above and:

```text
--implementation-head <exact reviewed implementation head>
--output-root /mnt/d/DeadlyCatCoding/STSRL/artifacts/t108-root-occurrence-mapping-subreason-diagnostic-41a789a/full-323-attempt-1
--native-binary <fresh T107-pin build path>
--native-binary-sha256 <independently verified SHA-256>
--readiness-approval <exact-head Maintainer readiness JSON>
--worker-count 4
--lower-worker-reason "Reuse T106's accepted four-worker resource calibration and guard."
```

Do not add `--candidate-positions` for the full population. Any canary output
remains non-authoritative and must use a separate attempt directory. Each
attempt refuses to overwrite retained rows, report, execution record, or
manifest. A successful census requires exactly 323 valid rows; partial output
cannot be combined with another attempt.
