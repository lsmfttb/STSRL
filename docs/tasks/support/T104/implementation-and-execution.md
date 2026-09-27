# T104 implementation and execution binding

This accompanies the [approved T104 contract](../../T104-particle-bridge-failure-localization.md).
It records implementation choices and a reproducible command, not a diagnostic
result or authorization to execute. Maintainer independently reviews the exact
implementation head before any native canary or census.

The entrypoint is `python -m sts_combat_rl.commands.t104_bridge_localization`.
The reusable diagnosis is in `sim/t104_bridge_localization.py`. It reuses the
accepted T103 restore and full pre-bridge projection/candidate/action/order/
context/completeness checks. A read-only observation hook leaves T103 baseline
classification and native call arguments unchanged. Both lanes create fresh
adapters and restore independently. The standalone lane calls only the accepted
sampler, never full bridge or Search.

## Public surfaces and evidence

Rows preserve two explicitly named pre-call surfaces:

- `baseline_P0`: the T014 `native-public-projection-v1` canonical payload used
  by accepted T103, with replay-only action bits removed;
- `P0`: the existing T096 public-information projection read on the same bridge
  clone immediately before the frozen call, validated with the accepted public
  projection validator.

T099 anchor and particle projections are T096 surfaces. Part A first-drift
classification uses comparable T096 `P0 -> A -> Pi` evidence. Exact T014-to-
anchor differences remain separately named baseline representation evidence;
they are not presented as native public-state mutation. Every row names APIs
and observed schema IDs. Missing comparable observations remain explicit and
can yield the published opaque localization class. No normalization guesses
fields or suppresses differences. Diffs retain canonical missing/type/unequal
paths, ordered public identities and duplicate occurrences. Invalid/private
trees are rejected before paths are generated, including hidden-intent fields
when enemy intent is classified hidden. Neither raw bridge reports nor private
standalone audit rows are persisted.

The standalone N=2 probe preserves accepted T098 batch completeness, ordered
indices, public projection/action fidelity, hidden-intent absence, and required
audit-digest schema checks. Digests are inspected transiently and never exported.
It imposes no N=32 witness or distribution-diversity requirement. Standalone
success and failure do not establish any monolithic internal outcome. Part B
classes and the independent observability predicate use structured facts only.
The aggregate rechecks that predicate and uses its exact count for the terminal.

## Input qualification and process execution

The retained [T103 execution record](../T103/maintainer-execution.md) owns the
scientific input identity. The command pins its accepted manifest, rows and
report hashes and producer, reuses accepted T101/T103 input qualification once,
and preserves historical B/C producer identities separately from the current
native consumer. The accepted terminal job-status bytes additionally hash to
`171e04a7271707513ae7310a71c9419cf08df3de3490c338610e97a387170d08`.
The command verifies that its Python/native module binding is the accepted
CPython 3.13.13 binary and records that runtime.

Qualification loads canonical sources once using the inherited boundary, then
drops unselected records before creating Linux `fork` process workers. Workers
inherit selected immutable restore maps through copy-on-write and receive only
their contiguous candidate jobs. No worker reloads or requalifies large pools.
Fork precedes native adapter initialization and thread setup; the command fails
closed if the parent already imported the native module or has active threads.
Native bindings remain unchanged and retain the GIL, so threads are not used.
The default process target is host logical CPUs, capped by selected candidates;
lower configured concurrency requires an explicit resource/tooling reason.
Reports retain configured workers, observed worker PIDs, effective workers,
record ranges, per-worker peak RSS and wall-clock costs. A reviewed bounded
canary must establish the memory budget before the full process census.

`--candidate-positions` accepts unique ascending indexes in the original frozen
413-record order. It does not change identities, source ordinals, seeds or
configuration. Partial runs write separate retained artifacts and have terminal
`INCOMPLETE`, with explicit canary reproduction/completeness facts. They cannot
claim either successful full-census terminal. A baseline contradiction produces
`T103_SUPPORT_RESULT_NOT_REPRODUCED`; workers stop before the next candidate
after the shared stop signal, letting already active native calls return.

## Reproduction command

Run through the repository detached-job/resource convention after Maintainer
review, with a unique T104 retained root outside disposable worktrees. Preserve
the complete argument array and resource-guard evidence in the job status.
For the reviewed native checkout, the full command is:

```bash
PYTHONPATH=/home/lsmft/stsrl-spikes/build-t101-native-97f59b6-py313:/mnt/d/deadlycatcoding/stsrl-t103/src \
/home/lsmft/stsrl-spikes/py313-torch/bin/python -m sts_combat_rl.commands.t104_bridge_localization \
  --implementation-head <reviewed-full-implementation-SHA> \
  --output-root /mnt/d/DeadlyCatCoding/STSRL/artifacts/t104-bridge-localization-<head>/full \
  --t103-retention-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t103-particle-search-support-domain-diagnostic-ec58e2a/t103-retention-manifest.json \
  --t103-execution-record /mnt/d/DeadlyCatCoding/STSRL/artifacts/t103-particle-search-support-domain-diagnostic-ec58e2a/jobs/t103-diagnostic.status.json \
  --native-binary /home/lsmft/stsrl-spikes/build-t101-native-97f59b6-py313/slaythespire.cpython-313-x86_64-linux-gnu.so \
  --t101-retention-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t101-bounded-particle-convergence-361a77d/admission/t101-terminal-retention-manifest.json \
  --t087-formal /mnt/d/DeadlyCatCoding/STSRL/artifacts/t087-formal-natural-413-8d7e44-20260911/t087-formal-natural-evidence.json \
  --t087-report /mnt/d/DeadlyCatCoding/STSRL/artifacts/t087-final-8d7e44-20260911/t087-dense-combat-diagnostics-report.json \
  --t087-retention /mnt/d/DeadlyCatCoding/STSRL/artifacts/t087-final-8d7e44-20260911/t087-retention-manifest.json \
  --t085-selection /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/selection/t085-native-selection.json \
  --t085-restore /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/selection/t085-native-selection-restore-evidence.json \
  --a-pool /mnt/d/DeadlyCatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl \
  --b-pool /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/source/cohort-b-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c/cohort-b-merged.pool.jsonl \
  --c-pool /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/source/cohort-c-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c/cohort-c-merged.pool.jsonl \
  --b-source-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/source/cohort-b-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c/cohort-b-source-manifest.json \
  --c-source-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/source/cohort-c-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c/cohort-c-source-manifest.json
```

For a representative 18-record canary, use a distinct `/canary` output root and
append `--candidate-positions 0 1 2 3 47 61 93 94 95 145 150 190 285 286 287 288 289 290`.
These are the first three accepted identities of each A/B/C-by-T103-class group,
selected from the exact retained ordered metadata, and give the 16-core host
16 configured process shards. The canary is a resource/reproduction check only.

Outputs are current-schema `t104-candidate-localization.json`,
`t104-aggregate-report.json`, and `t104-retention-manifest.json`. They bind exact
input provenance, output hashes/sizes, regeneration command, retention reason
and deletion condition. Retain raw evidence until audit and successor
observability consumers close. The code refuses to overwrite existing outputs.

No native canary, census, source generation, training or other large job was
started during implementation. Repository-wide baseline limitations remain the
12 inherited test failures and 528 Ruff diagnostics/24 format files documented
by T103; implementation verification uses focused relevant tests and changed
file checks, without expanding scope to repair those failures.
