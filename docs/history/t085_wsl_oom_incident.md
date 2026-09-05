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
