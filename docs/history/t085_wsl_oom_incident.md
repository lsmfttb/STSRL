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

## Formal Cohort-B outcome and remaining blocker

The formal v3 batch is now terminal. The admission-only root
`cohort-b-formal-v3-guarded-211cc58` produced 10/16 successful shards; its
other six shards failed in the original admission/lease execution boundary.
Because that batch started before the runtime-tripwire patch, its successful
shards are not runtime-guard evidence. A corrected-environment retry at
`cohort-b-formal-v3-retry-05b3f6e-envfix` produced 5/6 successful shards. The
five completed runtime guards reached `COMPLETED` without a trip, with peak
process-group RSS values of 1,874, 3,059, 1,965, 1,835, and 1,992 MiB under
the 6,144 MiB tripwire. Across both batches, 15/16 source-generation shards
published valid current-schema artifacts. WSL had approximately 22 GiB
available memory, zero swap use, no current-boot OOM evidence, and no
remaining T085 process after the batch ended.

The remaining shard-07 failure is not an OOM. With the accepted Python/native
pairing and the frozen `assist_hp75_potion` schedule, source seed 851450
reproducibly reached a native snapshot reporting
`screen_state=BATTLE`, `battle_active=true`,
`battle_outcome=PLAYER_VICTORY`, zero living monsters,
`battle_input_state=EXECUTING_ACTIONS`, top-level `outcome=UNDECIDED`, and an
empty legal-action list. The pinned native source enumerates no battle actions
for a non-`UNDECIDED` battle outcome, while the complete-run executor correctly
fails closed when the run has no legal action and no terminal transition. No
Python-side mechanics inference, fabricated transition, weakened validation,
or blind shard retry was used. The exact 1,024-run Cohort-B inventory therefore
remains incomplete, and no selection, restored evaluation, paired outcome, or
scientific T085 classification is claimed. Resolving this boundary requires a
compatible pinned native-simulator repair or an explicitly reviewed contract
recovery; it is not solved by the WSL resource guard.

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

The three formal Cohort-B v3 shards that were already running when this patch
was prepared were launched with the earlier admission-only wrapper. They were
not restarted or changed by this patch and are not evidence that the runtime
tripwire was active; their results must not be described as runtime-guard-
validated.

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
  --resource-runtime-rss-limit-mib 6144 \
  --resource-runtime-memavailable-floor-mib 4096 \
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

The illustrative 18 GiB aggregate reservation leaves roughly 6 GiB below the
observed 24 GiB WSL memory limit, while the 6 GiB per-shard RSS tripwire and
4 GiB available-memory floor are explicit operational choices rather than
measured hard-safe limits. They should be revisited when the host or workload
changes.

Admission requires the explicit `--resource-runtime-rss-limit-mib` process-group
RSS ceiling, and that ceiling cannot exceed the per-job
`--resource-memory-request-mib` reservation. The supervisor samples aggregate
RSS for the target process group;
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
