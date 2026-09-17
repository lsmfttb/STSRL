# T092 Formal 413-Start Collection Readiness

This is an execution recipe only.  It is not a formal authorization and must
not be used until the Maintainer records `FORMAL_AUTHORIZED` for the exact PR
head and reviews a valid retained 12-start canary evidence artifact.

`python -m sts_combat_rl.commands.t092_formal prepare-authorization` admits:

- the immutable T090 split manifest (exactly 413 entries, A/B/C = 93/192/128);
- a hash-bound canonical T090 root-reference table (6,369 decisions, 159
  single-action, 6,210 multi-action, S0 = 309);
- the hash-bound accepted T092 paired-canary evidence;
- a formal restore-input manifest containing one immutable T087/T090 restore
  payload per source; and
- the ON native process specification for
  `a439c70b568eab78dea42fe857dab56fa27cda3f`.

`formal-input-identities.json` has exactly these fields:
`formal_restore_manifest`, `arm_process_specs`, `t087_source_cohort`,
`t090_source_ledger`, `t091_reference`, and `task_native_provenance`.  All but
`arm_process_specs` are `{path, sha256, size_bytes, schema_id}` identities.
The restore manifest repeats the four upstream artifact identities and maps
each of the 413 source identities to a separate
`t092-formal-restore-shard-input-v1` payload.  A worker reads only the payload
for the source it is running; it rejects a missing, conflicting, or unhashed
payload before native import.

Create those payloads once with `prepare-restore-inputs`; it performs accepted
artifact admission only (no native module, simulator, Search, or collection)
and uses create-only output under the supplied ignored artifact root.  This is
the only step that reads the large accepted restore source artifacts.  It must
be run once, not by every worker.

The approved runtime callable is
`sts_combat_rl.commands.t092_formal_runtime:t092_formal_runtime`.  It reads
only the one source restore payload needed by the current shard, verifies its
hash and source identity, then delegates to the existing fresh-process ON arm
boundary.  It cannot construct a simulator before the exact authorization and
native/source-root checks pass. Authorization preparation performs the full
canary schema/geometry validation once; each formal worker rechecks the exact
hash-bound canary reference by streaming its bytes and does not materialize the
large accepted canary JSON again.

The formal topology is eight canonical-ordinal-modulo shards and eight effective
workers.  The operational limit is 2 GiB per worker (16 GiB aggregate); this
is deliberately lower than host CPU count because the earlier selected-start
admission probe reached approximately 2.5 GiB RSS.  The collector retains one
compact shard at a time; full internal-node corpora are never a required
in-memory aggregation input.  Each source is executed exactly once, with exact
checkpoint restoration/no reseed and the inherited explicit 500-step envelope.
Cap exhaustion remains a failure, never a successful terminal.

The formal finalizer validates every shard, replays the canonical root evidence
comparison before internal-surface metrics, applies cross-split exclusion and
within-split deterministic fingerprint deduplication for every registered
`n_min={1,2,4,8,16}`, and emits the source/worker ledger, shard identities,
cost/density/diversity/action-space/ambiguity reports, terminal classification,
and successor decision.  Retention output must be under an ignored artifact
root and uses create-only writes plus SHA-256/size identities.

Example commands are intentionally incomplete until paths and the Maintainer
authorization exist:

```bash
python -m sts_combat_rl.commands.t092_formal prepare-authorization \
  --implementation-head <exact-pr-head> --split-manifest <t090-split.json> \
  --root-reference <t092-t090-root-reference.json> \
  --canary-evidence-reference <canary-artifact-reference.json> \
  --input-identities <formal-input-identities.json> \
  --artifact-root <ignored-retention-root> --output <ignored-retention-root>/authorization-prep.json

# Only after a separate exact-head FORMAL_AUTHORIZED record:
python -m sts_combat_rl.commands.t092_formal run-shard \
  --authorization <formal-authorization.json> --shard-index 0 \
  --runtime-factory sts_combat_rl.commands.t092_formal_runtime:t092_formal_runtime \
  --implementation-head <exact-pr-head> --split-manifest <t090-split.json> \
  --root-reference <t092-t090-root-reference.json> \
  --canary-evidence-reference <canary-artifact-reference.json> \
  --input-identities <formal-input-identities.json> \
  --artifact-root <ignored-retention-root> --output <ignored-retention-root>/shard-00.json
```
