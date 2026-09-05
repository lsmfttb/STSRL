# T085 WSL OOM Incident And Bounded Source-Generation Repair

Date: 2026-09-05

This note records the operational failure and the bounded repair used while
executing T085. It is historical evidence, not a replacement for the T085
task contract or the accepted scientific result.

## Incident

Before the repair, five Cohort-B source-generation batches were attempted:
the initial batch, retry-v2, retry-v3, retry-v4, and formal-v1. Together they
submitted 80 shard supervisors and produced zero valid Cohort-B records. The
retry-v3 failures were deterministic runtime/import failures; the other stale
batches did not produce usable output. The formal-v1 batch used the correct
Python/native identities and ran at high CPU load, but WSL terminated the
batch before any shard could publish a valid pool.

The failure was a WSL global out-of-memory event, not a Windows host reboot.
The Windows host `LastBootUpTime` was unchanged while the previous WSL boot's
kernel journal reported `python invoked oom-killer`, swap exhaustion, and an
OOM-killed Python process with approximately 6.5 GiB anonymous RSS. The WSL
configuration at the time was 24 GiB memory, 8 GiB swap, and 16 processors;
the host had approximately 33.6 GiB physical memory. The WSL shutdown also
terminated unrelated Codex processes as victims. No evidence shows that Codex
initiated the WSL shutdown.

## Repair

The external T085 contract remains 16 source shards and 16 effective workers.
The implementation now bounds the lifetime of the simulator state inside each
Cohort-B shard:

- collect exactly one source seed with a fresh adapter;
- close or shut down the adapter, delete references, and run garbage
  collection before the next seed;
- write each one-seed result to a temporary current-schema JSONL chunk and
  stream-merge those chunks without retaining all simulator objects;
- strip temporary inner-merge provenance at the externally visible 64-seed
  shard boundary, preserve source-run identities with an explicit offset, and
  publish the final pool atomically only after validation succeeds.
- serialize only the memory-heavy Cohort-B finalization interval with an
  artifact-root file lock shared by processes using that root; release the
  artifact reference and run garbage collection/native heap trimming before
  releasing the lock. Collection remains parallel across the 16 workers.

The detached-job supervisor was repaired at the same boundary. Its Unix
signal handler now records the signal and best-effort terminates the target
process group; the outer wait path performs the single target reap and writes
the terminal failure status. This removes the previous reentrant wait/deadlock
that could leave a killed target reported as `RUNNING`.

No `.wslconfig` change and no manual `wsl --shutdown` was used as part of this
repair. Long simulator stages are launched through the detached-job
convention, with explicit status/log paths and no reuse of failed output
directories.

## Verification boundary

The repair passed this focused suite (`72 passed`) using the project Python
runtime: `test_t085_native_execution.py`, `test_assisted_source_generation.py`,
`test_lightspeed_adapter.py`, and `test_detached_job.py`. Compileall,
changed-file Ruff/format checks, and `git diff --check` also passed. The memory
boundary includes explicit `LightSpeedAdapter.close()` native-state release
and Unix `malloc_trim(0)` after each one-seed chunk. A one-shard bounded canary
was then launched with
the accepted Python/native identities. Its temporary chunks showed bounded
per-seed progress; sampled RSS briefly reached approximately 1.8 GiB and
later fell back to approximately 0.3--0.9 GiB. WSL retained approximately
21--22 GiB available memory with zero swap use and no OOM occurred. The canary
is diagnostic only and is not a formal Cohort-B input.

Formal Cohort-B generation and downstream T085 selection/evaluation remain
unaccepted until their detached statuses reach a terminal state and their
pool, manifest, restore/parity, outcome, retention, and scientific
classification gates are independently verified. The final accepted result
must be recorded in `docs/current_status.md` and the T085 artifact/retention
manifests after those gates complete.

## Follow-up bounded-run boundary

The first formal Cohort-B shard also exposed a non-OOM boundary: a normally
bounded run can end with `terminal=false` while its ordered source summary and
run identity remain structurally usable. The earlier validator treated every
such truncation as a source-pool failure. The follow-up repair retains the
complete 1,024-run inventory, records the run as `source_valid=false` with
`failure_reason=bounded_run_truncated`, and leaves
`complete_source_identity` null rather than inventing a checkpoint identity.
B selection filters that run; malformed source structure, execution problems,
provenance failures, and missing or duplicate required identities remain
fail-closed. This makes bounded truncation a manifest-level invalid run, not a
source-pool structural failure. Outputs from the old code that was still
running at that observation are diagnostic only and are not accepted results.

## Prevention of recurrence

The persistent WSL journal confirms that the earlier batch suffered repeated
`global_oom` events, with Python processes killed as victims. Repeated shard
and retry launches also created a risk that a second copy of the same batch
would consume memory while the first copy was still active. The observed
environment was approximately 24 GiB of WSL memory, 8 GiB of swap, and a
32 GiB Windows host. This section records an operational guard for participating
jobs; it does not claim that an unguarded process or a WSL VM-layer issue is
resolved.

`scripts/run_detached_job.py` now has an opt-in POSIX resource admission lease.
All T085 long-running shard supervisors must use one shared
`--resource-root`, a stable `--resource-batch-id`, and a unique
`--resource-job-id` (the shard id). They also declare an aggregate memory
budget and per-job reservation. For example, a T085 Cohort-B shard launch can
use:

```text
python scripts/run_detached_job.py start \
  --status <shard>/status.json --stdout <shard>/stdout.log \
  --stderr <shard>/stderr.log \
  --resource-root <t085-artifact-root>/admission \
  --resource-batch-id t085-formal-b --resource-job-id shard-00 \
  --resource-stage t085-cohort-b-source \
  --resource-memory-budget-mib 18432 \
  --resource-memory-request-mib 6144 \
  --resource-runtime-rss-limit-mib 7168 \
  --resource-wait-seconds 3600 \
  --resource-worker-count 16 --resource-shard-count 16 \
  -- <the frozen 16-worker T085 command>
```

The example reserves at most three such shards concurrently when the shared
root has no other leases; remaining shards wait up to the explicit limit and
then fail clearly. A duplicate active `(batch_id, job_id)` is rejected rather
than starting a second copy. The supervisor status records the requested and
aggregate budgets, admission state/reason, admitted concurrency, batch/shard
identity, and the fixed 16-worker/16-shard declaration. Lease cleanup runs on
normal exit, target failure, supervisor exceptions, and Unix signal cleanup;
kernel-held file locks also make a lease from a killed supervisor reclaimable.

Admission requires the explicit `--resource-runtime-rss-limit-mib` process-group
RSS ceiling. The supervisor samples aggregate RSS for the target process group;
if the ceiling is exceeded, it records a `TRIGGERED` runtime-guard state, sends
`SIGTERM` to the group, escalates to `SIGKILL` only after the bounded termination
grace period, then performs the sole outer wait/reap before releasing the lease.
The terminal status retains the trigger reason, sample count, observed/peak RSS,
timestamps, and final `RELEASED` lease state. An optional
`--resource-runtime-memavailable-floor-mib` records and enforces a Linux/WSL
`MemAvailable` floor using the same fail-closed guard. These are sampled
runtime tripwires: they are not cgroups, do not reserve or cap unrelated WSL
processes, and a process can briefly exceed a limit between samples. A guard
observation failure is treated as a trip rather than silently continuing.

Ordinary small detached jobs omit all resource options and retain their prior
behavior and retain the legacy disabled resource-status shape. The guard is
therefore not automatic for jobs launched outside this explicit wrapper and
does not change T085's per-shard `worker_count=16` contract. No `.wslconfig` change
or `wsl --shutdown` is part of this protection, and no simulator job was
started by this documentation/code change.
