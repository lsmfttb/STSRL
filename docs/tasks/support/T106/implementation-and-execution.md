# T106 implementation and execution handoff

The command is `python -m sts_combat_rl.commands.t106_failure_stages` under the
WSL Python 3.13.13 environment containing the exact T105 native build. It does
not run a simulator during input qualification. It reuses the T104 and T103
retained artifacts in the stable primary checkout; no source pool is copied to
this worktree. The T104 paths must resolve to `full-attempt-2/` and its sibling
`jobs/census-attempt-2.status.json`. The native binary must be supplied with its
independently verified SHA-256. All remaining source arguments are the same
accepted T101/T104 paths documented in
[`T104 implementation and execution`](../T104/implementation-and-execution.md).
The Maintainer's prepared T105-pin WSL build is
`/home/lsmft/stsrl-spikes/build-t106-native-5afae22-py313/slaythespire.cpython-313-x86_64-linux-gnu.so`,
SHA-256 `5c30a764470e71b3e7b75e97aaecfd6d51b5c1dc9feaf3455140108069ec4019`;
that build has not been used for a T106 population replay.

Required T106 arguments are `--implementation-head`, `--output-root`,
`--t104-rows`, `--t104-report`, `--t104-manifest`, `--t104-execution`,
`--t103-retention-manifest`, `--t103-execution-record`,
`--t101-retention-manifest`, `--native-binary`,
`--native-binary-sha256`, and the ten T087/T085/source pool and source manifest
arguments used by T104. `--candidate-positions` names ascending indexes in the
343-row Part-B subset, starting at zero; it is for a bounded canary and cannot
establish the successful census terminal. Contradiction terminals still take
precedence over `INCOMPLETE`. The full population is selected by omitting it.
The command refuses to overwrite any of its four retained output files.

For the full 343-row execution, the command additionally requires
`--full-readiness-approval` pointing to a JSON document issued after Maintainer
review of the exact implementation head and resource plan. Required fields are:

```json
{
  "task_id": "T106",
  "implementation_head": "<exact current 40-character commit>",
  "full_execution_authorized": true,
  "approval_comment_url": "https://github.com/lsmfttb/STSRL/pull/122#issuecomment-<id>",
  "worker_count": 4,
  "resource_plan": {
    "supervision": "detached_resource_guard",
    "summed_rss_limit_mib": 16384,
    "mem_available_floor_mib": 8192,
    "sample_interval_s": 1,
    "status_path": "<stable ignored T106 job status path>"
  }
}
```

The full-run candidate is four WSL Linux fork workers with four contiguous
Part-B-order shards: `[0,86)`, `[86,172)`, `[172,258)`, and `[258,343)`.
This follows T104's observed six-worker summed-RSS guard
trip and successful four-worker attempt. Keep the 16,384 MiB summed-RSS limit,
8,192 MiB MemAvailable floor, and one-second sampling; use the repository
detached job resource guard. The T104 input-qualification phase took about
1,045 seconds and four-worker replay about 11,028 seconds. These are planning
estimates only. A bounded canary at four workers should verify T105 trace
decoding and measure T106-specific resource/time behavior before the Maintainer
approves the full job. No T106 canary or full job was launched for this handoff.

The command retains rows, aggregate report, execution record, and a hash-bound
retention manifest under the caller's stable ignored output root. A row carries
the T104 historical stratum as a covariate, the current T105 pin separately,
the exact bridge call, immediate T105 snapshot, a telemetry-only class, and a
bounded exception signature for audit. The command stops subsequent shard work
on a baseline contradiction or invalid trace; terminal precedence is baseline
contradiction, then telemetry violation, then complete census, otherwise
`INCOMPLETE`. Partial evidence remains retained for review. The generated
report is diagnostic only and cannot qualify repair or convergence work.
