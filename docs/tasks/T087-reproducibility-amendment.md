# T087 Reproducibility Amendment

This file is a **normative part of the T087 specification bundle** and must be read together with `T087-dense-combat-outcome-diagnostics.md`.

It closes the reproducibility gaps identified by Maintainer review on PR #100 at task-contract head `9a078bb84e8bb28443886ea9418b2c5ec4398945`. Where this amendment is more specific than the primary T087 document, this amendment controls. It does not change T087's scientific question, cohort, controller, native identity, diagnostic formulas, HP ladder values, human-review role, or successor boundary.

No implementation or formal simulator execution is authorized until Maintainer approves an exact PR head containing this amendment.

## 1. Canonical record-selection bytes

For every T087 ranking that previously referred to `canonical_record_identity_bytes` or `canonical_run_identity_bytes`, use the exact T085 `T085BattleStartRecord.selection_identity` string for that selected record.

The accepted T085 definition is occurrence-safe:

```text
if source_artifact_record_identity is present:
    selection_identity = source_artifact_record_identity
else:
    selection_identity = source_run_identity + ":" + battle_identity
```

Define exactly:

```text
selection_identity_bytes = selection_identity.encode("utf-8")
```

No JSON wrapping, Unicode normalization, whitespace transformation, case conversion, path normalization, filename, artifact path, or other representation may replace these bytes.

### HP-rescue ranking

For every eligible natural loss record compute:

```text
selection_digest = sha256(
    b"T087-hp-rescue-v1\n" + selection_identity_bytes
).hexdigest()
```

Within each required cohort A/B/C, sort ascending by the tuple:

```text
(selection_digest, selection_identity_bytes)
```

and take the first eight.

### Blind-human-audit ranking

For every record eligible for a requested audit stratum compute:

```text
selection_digest = sha256(
    b"T087-human-audit-v1\n" + selection_identity_bytes
).hexdigest()
```

Within that stratum, sort ascending by:

```text
(selection_digest, selection_identity_bytes)
```

and take the required rows under the frozen threshold-relaxation procedure in section 3 below.

### Selection-manifest serialization and digest

The HP-rescue selection manifest and blind-audit selection manifest must each retain, in final selected order, at least:

- selection role/domain;
- cohort or audit stratum;
- zero-based selected rank within that cohort/stratum;
- exact `selection_identity` string;
- exact hexadecimal `selection_digest`;
- exact source selection-manifest identity inherited from T085.

For the digest-bearing canonical payload, serialize the manifest object as UTF-8 JSON using exactly:

```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

with no trailing newline added to the digest bytes. The retained SHA-256 is the lowercase hexadecimal digest of exactly those bytes. The artifact writer may add surrounding storage metadata only if the canonical digest payload is retained separately and byte-recomputable.

Any duplicate `selection_identity` among records eligible for one ranking domain, or any mismatch between retained identity bytes, digest, rank, and recomputed ordering, is `INCOMPLETE`.

## 2. T085 baseline randomness and evaluator binding

The primary T087 wording "reuse the exact T085 baseline@100 record-level Search randomness/seed plan" is superseded by the following exact contract.

T087 natural evaluations and every HP-rescue ladder variant must reuse the accepted T085 restored-record execution boundary, not invent a new Search seed namespace.

Accepted binding:

- T085 scientific run head: `5edaa255959d34d4d31bbfae7e6b6bed9758024d`;
- T085 selected-manifest SHA-256: `d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752`;
- T085 restore-evidence SHA-256: `0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef`;
- T085 paired-report SHA-256: `f756c9f4ac885c61c2a73ff9b2d0e05a15b317df2cce9c9bf5dbd374f7afcec3`;
- native identity: `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d62ff35579b54d70a7428afdf84743c94df3fe0c`.

For each formal T087 natural record:

1. resolve the exact canonical T085 record and restore it through the same accepted restore/parity boundary;
2. after successful restore, do **not** reset or reseed the simulator for Battle evaluation;
3. execute the Battle through the repository-owned controlled-run boundary equivalent to the accepted T085 baseline arm:

```python
execute_controlled_run(
    adapter,
    controller,
    seed=None,
    max_steps=200,
    action_space=ActionSpaceConfig.initial_no_potions(),
)
```

4. controller semantics are exactly unguided native Search v2@100, `highest_mean`, with both policy-prior and learned-leaf-value callbacks absent;
5. there is **no additional Python, controller, or per-record Search seed**. T087 must not derive one from cohort, record identity, source-run seed, shard, worker, wall clock, or task seed;
6. Search uses the native simulator/RNG state established by restoring that exact checkpoint. T087 may rely only on the state produced by the accepted restore; it must not separately reconstruct, perturb, or reseed native RNG state;
7. the 200-step controlled Battle cap is part of the inherited evaluator boundary. Reaching that cap while non-terminal is `INCOMPLETE`, not a loss and not a dense terminal row.

For each HP-rescue ladder variant, begin again from the exact same canonical record restore boundary, then apply only the accepted HP-addition Battle-start transform for the requested extra-HP value before starting the same `seed=None`, `max_steps=200` Battle evaluator. No potion/encounter transform, extra reset, explicit Search seed, or retry-until-stable operation is permitted.

T087 is not required to reproduce byte-identical action traces from the historical T085 paired report; it is required to reproduce the **accepted evaluator/randomness contract** above from the same restored-record identity. Any implementation that supplies an additional Search/controller seed or changes the 200-step evaluator boundary is `INCOMPLETE`.

## 3. Frozen blind-audit threshold relaxation

The primary T087 document's unspecified "deterministic threshold-relaxation rule" is superseded by this exact procedure. Selection is performed only after all 413 valid natural dense rows exist. Trace contents must not be inspected before the 24 identities are frozen.

All three audit groups must be pairwise disjoint and contain exactly eight records.

### 3.1 Wins

Let `W` be all authoritative natural victories. Rank all `W` with the T087 human-audit digest from section 1 and select the first eight.

If `len(W) < 8`, T087 is `INCOMPLETE`.

### 3.2 Near-boundary losses

Let `L` be all authoritative natural losses. Consider upper thresholds in exactly this order:

```text
0.25, 0.35, 0.50, 0.65, 0.75, 1.00
```

For each threshold `t` in order, define candidates as losses satisfying:

```text
enemy_hp_remaining_fraction <= t
```

Choose the **first** threshold with at least eight candidates. Rank those candidates by the human-audit digest and select the first eight. Record the selected threshold in the manifest.

If no threshold supplies eight valid candidates, T087 is `INCOMPLETE`.

### 3.3 Deep losses

Remove the eight selected near-boundary loss identities from `L` before selecting deep losses.

Consider lower thresholds in exactly this order:

```text
0.75, 0.65, 0.50, 0.35, 0.25, 0.00
```

For each threshold `t` in order, define candidates among the remaining losses satisfying:

```text
enemy_hp_remaining_fraction >= t
```

Choose the **first** threshold with at least eight candidates. Rank those candidates by the human-audit digest and select the first eight. Record the selected threshold in the manifest.

If no threshold supplies eight valid candidates, T087 is `INCOMPLETE`.

No other threshold, quantile, margin, cohort-balancing rule, manual substitution, or interesting-trace selection is allowed. The relaxation procedure may inspect only the already-frozen authoritative outcome and `enemy_hp_remaining_fraction` fields needed by these predicates; it may not inspect trace content or human judgment.

## 4. Acceptance impact

T087 can receive `SPEC APPROVED` only on an exact PR head containing both the primary task document and this amendment.

The existing T087 terminal classes remain unchanged:

- `DENSE_COMBAT_DIAGNOSTICS_READY` only when all primary-contract requirements and this amendment pass;
- otherwise `INCOMPLETE` at the task's frozen failure boundary.

This amendment requires no native change and authorizes none.
