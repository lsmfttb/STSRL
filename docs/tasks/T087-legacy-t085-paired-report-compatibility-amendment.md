# T087 Legacy T085 Paired-Report Compatibility Amendment

This file is a **normative part of the T087 specification bundle** and must be read together with:

- `T087-dense-combat-outcome-diagnostics.md`;
- `T087-reproducibility-amendment.md`;
- `T087-terminal-monster-telemetry-amendment.md`.

It resolves the bounded-canary blocker discovered after the exact T087 input files were loaded successfully. The accepted T085 paired report is a historical retained artifact whose exact pinned bytes predate the later top-level provenance layout assumed by the first T087 reader.

This amendment does not alter the T085 artifact, its SHA-256, T087's cohort, controller, native identity, dense metrics, HP-rescue semantics, or human-audit role. It authorizes only a fail-closed compatibility validation for this one already-pinned historical artifact shape.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: exact T085 paired-report artifact with schema `t085-paired-evaluation-report-v1` and SHA-256 `f756c9f4ac885c61c2a73ff9b2d0e05a15b317df2cce9c9bf5dbd374f7afcec3`; its top-level `selection_binding`; every retained row in its top-level `outcomes` sequence; the exact T085 historical native identity `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d62ff35579b54d70a7428afdf84743c94df3fe0c`; and the exact T087 selection/restore artifacts already bound by the primary contract.

Reuse mode: `scientific_quality_claim` only inside T087's diagnostic-validity boundary. This amendment does not authorize a new T085 result, a rewritten T085 artifact, a learned target, reward, Search heuristic, or controller-promotion claim.

Claim boundary: this amendment may establish only that the exact pinned legacy T085 paired report carries the required T085 task/native provenance redundantly at row level even though those two fields are absent at report top level, and that T087 may verify those facts by exhaustive row validation before admitting the report. It does not allow provenance inference from filenames, repository constants, paths, other artifacts, majority vote, or a subset of rows.

Required predicates: exact paired-report SHA-256 and schema; top-level `selection_binding` present and validated under the existing T087/T085 binding rules; exact legacy top-level absence of `task_id` and `native_execution_provenance` rather than conflicting values; non-empty top-level `outcomes` sequence; every outcome row is a mapping; every outcome row explicitly carries `task_id == "T085"`; every outcome row explicitly carries a mapping-valued `native_execution_provenance`; every such row provenance explicitly carries `native_identity` exactly equal to the historical T085 native identity; no row may be skipped, substituted, repaired, filename-inferred, or accepted by majority consistency.

Unavailable-fact behavior: if any required row, `task_id`, `native_execution_provenance`, nested `native_identity`, selection binding, artifact hash, schema, or exact legacy-shape fact is missing, malformed, conflicting, or unavailable, T087 fails closed to `INCOMPLETE` before simulator execution.

## 1. Frozen historical artifact identity

The only paired report eligible for this migration is exactly:

```text
schema_id: t085-paired-evaluation-report-v1
sha256: f756c9f4ac885c61c2a73ff9b2d0e05a15b317df2cce9c9bf5dbd374f7afcec3
```

The retained file must not be rewritten, normalized, copied into a new "current schema" artifact, or assigned a replacement scientific identity merely to satisfy T087.

The existing hash-bound artifact reader remains mandatory before this compatibility rule is considered.

## 2. Legacy-shape discriminator

For the exact pinned artifact above, the compatibility path is allowed only when all of the following are true:

1. top-level `schema_id` is the pinned schema;
2. top-level `selection_binding` exists and is a mapping;
3. top-level `task_id` is **absent**;
4. top-level `native_execution_provenance` is **absent**;
5. top-level `outcomes` exists as a non-empty sequence of mappings.

A present-but-wrong top-level `task_id` or a present-but-malformed/conflicting top-level `native_execution_provenance` is not a legacy case and must fail closed. The migration must not discard or override a conflicting top-level fact.

## 3. Exhaustive row-level task provenance

Let `R` be the exact top-level `outcomes` sequence in retained order.

For **every** row `r` in `R`, require:

```text
r["task_id"] == "T085"
```

No row may be omitted because of cohort, arm, budget, terminal outcome, failure status, or whether T087 later consumes that row directly.

If any row lacks `task_id`, carries another value, or is not a mapping, the paired report is unavailable for T087 and the task is `INCOMPLETE`.

Only after every row passes may the T087 reader set an internal validation fact equivalent to:

```text
paired_task_identity_verified = true
```

The reader must not mutate the loaded T085 document or synthesize a top-level `task_id` field in retained output.

## 4. Exhaustive row-level native provenance

For **every** row `r` in the same exact `outcomes` sequence, require:

```text
r["native_execution_provenance"] is a mapping
r["native_execution_provenance"]["native_identity"]
    == {
         "repository": "lsmfttb/sts_lightspeed",
         "ref": "refs/heads/stsrl/main",
         "commit": "d62ff35579b54d70a7428afdf84743c94df3fe0c"
       }
```

The comparison is structural equality of the mapping values required by the accepted historical T085 identity. Do not infer the commit from T087's source manifest, from the current simulator identity, from a file path, or from another outcome row.

Different arms/budgets may legitimately carry other row-level provenance fields that differ. This migration therefore does **not** require entire `native_execution_provenance` mappings to be byte-identical across rows; it requires every row's explicit nested `native_identity` to equal the same accepted T085 historical identity.

If any row lacks the mapping or nested identity, or any nested identity differs, T087 is `INCOMPLETE` before simulator execution.

Only after every row passes may the reader set an internal validation fact equivalent to:

```text
paired_native_identity_verified = true
```

Again, do not mutate the historical T085 document or create a replacement top-level provenance object and present it as original evidence.

## 5. Selection binding remains top-level evidence

Maintainer inspection established that the pinned paired report already contains the expected top-level `selection_binding`, including A/B/C/B@400 selected-identity orders.

That existing top-level binding must continue to be validated directly. The legacy migration is **only** for the missing top-level task/native provenance fields; it does not permit reconstructing, replacing, or weakening `selection_binding`.

The T087 natural cohort still uses only exact A/B/C records, while B@400 remains independently verified historical binding evidence as required by the existing T087 implementation contract.

## 6. Reader implementation rule

The T087 paired-report validator must implement a sequential branch:

```text
if valid top-level task_id and native_execution_provenance are present:
    validate the current/top-level form normally
else if artifact SHA/schema exactly match the pinned legacy report
     and both legacy top-level fields are absent:
    validate every outcome row under Sections 3 and 4
else:
    fail closed
```

It is forbidden to implement this as:

- `paired_document.get("task_id", "T085")`;
- fallback to repository constants without row evidence;
- inspect only the first row;
- majority/consensus over rows;
- accept a missing `native_execution_provenance` because the file hash is known;
- rewrite the retained T085 artifact with newly injected top-level fields.

Focused regression coverage must prove at least:

1. the exact legacy shape passes when every row carries explicit matching task/native provenance;
2. one missing row `task_id` fails;
3. one conflicting row `task_id` fails;
4. one missing row `native_execution_provenance` fails;
5. one conflicting nested native commit fails;
6. a present conflicting top-level field fails rather than entering the legacy branch;
7. a different paired-report SHA cannot use this migration;
8. top-level `selection_binding` remains mandatory and independently validated.

## 7. Canary and formal-execution boundary

The previously authorized canary did not execute a simulator action, so it produced no scientific evidence to retain or invalidate.

After this amendment is implemented and independently reviewed on an exact PR head:

1. rerun the hash-bound T085 input gate;
2. require the legacy paired report to pass this exhaustive migration;
3. rerun the bounded one-record canary from the beginning;
4. report its exact record identity, command, artifact paths/hashes, terminal telemetry, and result;
5. do not begin the 413-record formal gate until Maintainer gives a new explicit formal authorization.

No native change is authorized by this compatibility amendment. The accepted T087 native identity remains `96052d24b9c2c16ff25b6f7241edd972613be997` unless separately changed under native-lineage governance.

## 8. Re-approval requirement

This is a material reproducibility-contract clarification because the first T087 reader required a top-level provenance layout that the exact accepted historical artifact does not have.

No further canary or formal execution is authorized until Maintainer re-approves an exact PR head containing this amendment and then independently reviews the implementation of the migration rule.
