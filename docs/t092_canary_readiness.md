# T092 paired 12-start canary readiness

This is plumbing only. It does not authorize, start, or imply a canary run.
The future approved runner restores every selected T087/T090 checkpoint twice:
OFF uses the unchanged `battle_search_v2` API and ON uses
`battle_search_v2_with_internal_teacher_telemetry`. Each arm advances through
`execute_controlled_run`; each Battle decision retains ordered root actions,
visits, evaluation sums/means, selected action, and Search counters. The ON
arm additionally retains parsed public-only internal occurrences. The evidence
validator fails the pair on any root decision-sequence/root-semantic mismatch,
terminal outcome/current-HP/decision-count mismatch, missing restore
public/legal parity, malformed cost, or missing/extra pair or arm fields.

Provenance is arm-specific: OFF is bound to publication native
`20a6c2b3a9cea817c988178b814f083ff889853f` on `refs/heads/stsrl/main`; ON is
bound to the task telemetry native
`07e1770cf0710d8c26719c153383d09e3bfd7686` on
`refs/heads/planner/t092-internal-search-state-telemetry`. Both arms bind the
full `t092-frozen-search-v2-teacher-config-v1` envelope. The frozen envelope
is still Search-v2@400, no potions, highest-mean root selection, no policy
prior/learned leaf, `playoutRandom`, and `evaluateEndState`.

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

The worker plan is 12 shards / 12 workers, one selected start per shard. Each
shard launches two fresh, distinct Python OS processes: OFF loads only the
publication extension and ON loads only the task extension. They share no
interpreter, module cache, simulator object, RNG object, or mutable restore
state; their only output pairing channel is two immutable arm records. The
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

## Detached execution entrypoint (authorization required)

`src/sts_combat_rl/sim/t092_canary_execution.py` provides the actual future
execution boundary. `execute_t092_authorized_canary_shard` runs exactly one
canonical selected start only after an exact Maintainer authorization binds the
STSRL implementation head, immutable split-manifest SHA-256, no-execution plan
SHA-256, exact restore-input identity map SHA-256, both arm native identities,
the frozen teacher envelope, 12-worker/12-shard topology, and output root.
It validates those facts before a runtime factory or adapter is imported.

The pinned native-free restore recipe is
`sts_combat_rl.commands.t092_canary_runtime:t092_canary_runtime`, and its
exact map is [t092_canary_runtime_identity_map.json](t092_canary_runtime_identity_map.json).
Before authorization preparation, one native-free, single-worker admission
must produce a private, immutable selected-12 restore payload and a derived
runtime identity map. It verifies the full accepted T087/T085 inputs exactly
once, records wall time and maximum RSS, and retains only the twelve selected
source/checkpoint records. It does not create a simulator, native extension,
or canary result:

```bash
PYTHONPATH=src /usr/bin/python3.14 -m sts_combat_rl.commands.t092_canary_execution prepare-restore-inputs \
  --implementation-head <exact-STSRL-head> \
  --artifact-root /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id> \
  --output /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/private/t092-selected-restore-inputs.json \
  --runtime-input-identities-output /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-runtime-input-identities.json
```

The prior read-only probe reached about 2.5 GB RSS and took multiple minutes,
so this admission is deliberately one worker only. Its recorded observed cost,
not a forecast, is the required resource evidence. The later twelve canary
shards read only the compact hash-bound payload; they must not reopen or parse
the 402 MB T087 evidence, 183 MB report, or multi-GB T085 pools. After the
compact map is bound into authorization, the callable returns exactly `arm_process_specs`,
`source_records`, and `canonical_records`. The command invokes the recipe with
the hash-bound runtime identity map and authorized implementation head; it returns no native adapter or
factory. The launcher validates each arm's interpreter, one extension path,
size, SHA-256, and native identity before spawning that arm. The child repeats
the binary check before constructing `LightSpeedAdapter`, writes its immutable
`t092-paired-canary-arm-record-v1` JSON once, and the parent independently
reads/validates both records before offline pairing. T092 neither guesses maps
nor reconstructs them from checkpoint bytes. It must first write a
non-authorizing template:

```bash
PYTHONPATH=src python3 -m sts_combat_rl.commands.t092_canary_execution prepare-authorization \
  --implementation-head <exact-STSRL-head> \
  --split-manifest /mnt/d/DeadlyCatCoding/STSRL/artifacts/t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json \
  --runtime-input-identities /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-runtime-input-identities.json \
  --artifact-root /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id> \
  --output /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-canary-authorization-preparation.json
```

Only after a separate Maintainer `CANARY_AUTHORIZED` attestation replaces that
template with the exact authorization record may the following detached launcher
be used. It launches twelve independent one-start shards; it is not invoked by
this PR.

```bash
scripts/run_t092_canary_detached.sh \
  <exact-STSRL-head> \
  /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-canary-authorization.json \
  /mnt/d/DeadlyCatCoding/STSRL/artifacts/t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json \
  /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>/t092-runtime-input-identities.json \
  sts_combat_rl.commands.t092_canary_runtime:t092_canary_runtime \
  /mnt/d/DeadlyCatCoding/STSRL/artifacts/t092-canary-12-<authorization-id>
```

The launcher writes two immutable arm records under `arms/`, then one immutable
`t092-paired-canary-shard-v1` JSON per shard under `shards/`, plus detached
status/stdout/stderr files under `jobs/`. Each pair includes the canonical
selected source, two distinct arm artifact paths/SHA-256s, pair SHA-256, arm
identities, worker topology, input-map SHA-256, and exact authorization ID. The merger
accepts only all twelve canonical shard positions and writes one
`t092-paired-semantic-parity-canary-v1` evidence JSON; every retained JSON is
written once with its SHA-256, size, and schema returned for the eventual
retention manifest. Outputs are ignored artifacts, never Git inputs.

The launcher retains all 12 logical shard positions but requires explicit
`T092_CANARY_RESOURCE_*` budget, per-shard reservation, RSS-limit, and
MemAvailable-floor values. Its detached resource leases admit only the number
of workers justified by those values; remaining shard supervisors wait rather
than oversubscribing memory. The values must be selected from the compact
admission record and the separately authorized resource plan, never inferred
from CPU count or silently defaulted to twelve concurrent simulators.

The process specification binds `/mnt/d/DeadlyCatCoding/STSRL-T092` as the
actual STSRL source root. Both parent and child run `git -C <source-root>
rev-parse HEAD` and fail closed before simulator construction unless it equals
the authorization's implementation head. The arm child's `PYTHONPATH` is that
same root's `src/` plus exactly one arm extension directory.
