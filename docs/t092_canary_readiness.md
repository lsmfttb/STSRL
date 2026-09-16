# T092 paired 12-start canary readiness

This is plumbing only. It does not authorize, start, or imply a canary run.
The future approved runner restores every selected T087/T090 checkpoint twice:
OFF uses the unchanged `battle_search_v2` API and ON uses
`battle_search_v2_with_internal_teacher_telemetry`. Each arm advances through
`execute_controlled_run`; each Battle decision retains ordered root actions,
visits, evaluation sums/means, selected action, and Search counters. The ON
arm additionally retains parsed public-only internal occurrences. The evidence
validator fails the pair on any root decision-sequence/root-semantic mismatch
or terminal outcome/current-HP/decision-count mismatch.

The deterministic, no-execution readiness command is:

```bash
PYTHONPATH=src python3 -m sts_combat_rl.commands.t092_internal_search_state canary-plan \
  --split-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json \
  --output /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-canary-plan.json
```

Inputs for a later authorized runner are that exact immutable split manifest,
the accepted occurrence-safe T087/T090 source-to-`T085BattleStartRecord` map,
the matching `BattleStartCheckpointRecord` map, native identity
`07e1770cf0710d8c26719c153383d09e3bfd7686`, and the frozen no-potion
Search-v2@400 configuration. Missing maps, restore parity, native identity, or
teacher envelope fail closed.

The worker plan is 12 shards / 12 workers, one selected start per shard, with
each worker running both arms serially for its own restored start. This is
capped by canary shard count and keeps paired restore state isolated. The
future output root is the ignored path shown above. It must contain the plan,
the exact pair evidence schema
`t092-paired-semantic-parity-canary-v1`, a source-entry SHA-256 ledger, ON-arm
internal occurrence rows, and a retention manifest with hashes and sizes.

The file-only validator is:

```bash
PYTHONPATH=src python3 -m sts_combat_rl.commands.t092_internal_search_state canary-validate \
  --split-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json \
  --evidence /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-paired-evidence.json
```

It validates pre-existing JSON only and does not instantiate a simulator.
