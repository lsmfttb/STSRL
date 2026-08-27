# T075 Normative Execution, Reuse, And Artifact Contract

This file is a **normative part of the T075 specification bundle** together with
`T075-leakage-safe-non-combat-cohort-repair.md`. It freezes the execution command
surface, retained-input identities, artifact schemas, deterministic edge cases,
and retention policy that were left too implicit in the first proposal.

If the primary T075 task document is less specific than this file, this file
controls. Any material change to a value, path rule, schema, ordering rule, or
command template below after exact-head approval requires Maintainer re-approval.
This file does not authorize implementation by itself.

## Frozen Runtime And Paths

Repository/runtime pairing for every WSL stage:

```text
repository_windows = D:\DeadlycatCoding\STSRL
repository_wsl = /mnt/d/DeadlycatCoding/STSRL
python = /home/lsmft/stsrl-spikes/py313-torch/bin/python
native_pythonpath = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
project_pythonpath = /mnt/d/DeadlycatCoding/STSRL/src
PYTHONPATH = ${native_pythonpath}:${project_pythonpath}
```

Stable T075 output root:

```text
artifacts/t075-leakage-safe-non-combat-cohort-repair
```

The exact compact output paths are:

```text
stage0-preflight.json
stage0-retained-source-reuse.json
stage0-retained-source-reuse.retention.json
stage1-replay-group-ownership-audit.json
stage1-selected-states.json
stage1-selection-manifest.json
stage1-selection.retention.json
stage2-target-table.json
stage2-target-table.retention.json
stage4-checkpoints/
stage4-training-report.json
stage4-training.retention.json
stage5-heldout-report.json
stage5.retention.json
stage6-complete-run-report.json
stage6.retention.json
terminal-decision-report.json
t075-retention-manifest.json
```

No generated T075 artifact may be placed under a different stable root merely
for convenience. Temporary shard files may live below a stage-local temporary
directory under this root and must be removed or referenced explicitly by the
final stage manifest after a successful merge.

## Exact Retained T065 Inputs

T075 reuses, and does not regenerate, these two GB-scale raw inputs:

| Arm | Exact path | Exact bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Each raw input must be readable by the current strict `t065-source-state-v1`
reader and must retain:

- approved T065 spec `a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`;
- simulator seeds exactly `650001..650256`;
- source driver seed exactly `654001`;
- the named source arm exactly;
- pinned current accepted simulator identity;
- battle controller provenance `oracle_search_v1_highest_mean_s20`;
- exact T065 `ActionSpaceConfig.initial_no_potions()` serialization;
- 16 source shards x 16 source seeds and 16 effective workers;
- 256 requested and 256 terminal source runs;
- zero truncated source runs;
- original per-run/source provenance and replay/public identities.

### Retained manifest resolution rule

The two source retention-manifest filenames are not re-invented by T075. Resolve
each source manifest deterministically as follows:

1. inspect only `*.retention.json` files in
   `artifacts/t065-learned-non-combat-policy-v1/`;
2. accept a candidate manifest only if its parsed retained-artifact entry names
   the exact raw-source path above and records the exact raw byte size and
   SHA-256 above, the matching source arm, approved T065 spec, source seed range,
   driver seed, pinned simulator identity, and 16-shard/16-worker evidence;
3. exactly one manifest must satisfy all predicates for each raw source;
4. zero or more than one matching manifest is T075 Case D at
   `source-input-reuse`;
5. copy the manifest's original source regeneration command(s) verbatim into the
   T075 reuse manifest as provenance-only text. T075 must not execute them.

This rule is intentionally content-addressed and unambiguous without guessing a
historical sidecar filename.

Additional accepted T065 evidence is fixed as:

```text
preflight_path = artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.json
preflight_sha256 = a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334
case_d_decision_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-deeaa46-retry2.t065-terminal-decision-report.json
case_d_decision_sha256 = 0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc
case_d_retention_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-deeaa46-retry2.retention.json
case_d_retention_sha256 = fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf
```

The preflight and Case-D evidence are lineage/audit inputs. The two raw Stage 1
source files are the only scientific source-candidate inputs.

## Candidate Domain Before Ownership

The selectable ownership domain is frozen before any grouping:

1. parse both retained source arms with the strict current reader;
2. keep only rows whose source-run record has `terminal == true`;
3. keep only the four mandatory families in this exact order:
   `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`;
4. require the row's simulator seed to map to the unchanged T065 seed-group split;
5. require all existing T065 public/model/action/provenance validation;
6. nonterminal/truncated rows remain countable source evidence but are not
   selectable and may never become owners.

The ownership audit must report, for each source arm and each family/split,
`raw_candidate_count`, `terminal_candidate_count`,
`nonterminal_excluded_count`, and `unsupported_family_excluded_count` before
replay grouping. A malformed or provenance-invalid row is Case D rather than an
ordinary exclusion.

## Frozen Group And Owner Identity

The T065 replay-equivalence key is unchanged:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON everywhere in T075 means UTF-8 JSON with sorted object keys,
compact separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, and no
trailing newline in the bytes used for a content digest. Persisted JSON files may
end with exactly one newline; file SHA-256 hashes the actual persisted bytes.

### Replay-group digest

The group payload is exactly:

```json
{
  "family": "<family>",
  "public_state_identity": "<identity>",
  "ordered_legal_action_identities": ["<the exact existing identity mappings in order>"]
}
```

The member mappings are the existing JSON-safe action-identity mappings, not
stringified Python values. Define:

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_payload_bytes = canonical_json(group_payload)
group_digest = sha256(T075_GROUP_DOMAIN + group_payload_bytes).hexdigest()
```

Groups are serialized in ascending `group_digest` order.

### Member ordering and the exact-tie edge case

For each member reuse the existing T065 key exactly:

```text
selection_digest = sha256(
  b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Members are serialized and compared in ascending lexicographic
`member_order_key` order.

If two or more distinct source rows in one replay group have **identical**
`selection_digest` and byte-identical `canonical_candidate_json_bytes`, the key
is not a total order. T075 must fail closed as Case D at `cohort-ownership` and
report every tied row's source arm, simulator seed, source run id, source step,
split, public-state identity, and group digest. Do not add source occurrence,
input order, worker completion order, private state, or another tie-break field.

If the key is unique, exactly the first member is the owner. All other members
are excluded before quota selection. The owner's split remains the split implied
by its unchanged simulator seed.

## T075 Artifact Schemas

All four schemas below are version 1. Required fields may not be omitted or
silently defaulted. Unknown additive fields are allowed only if they do not
change interpretation. Readers fail closed on missing required fields,
non-finite numbers, wrong ordering, parent-identity mismatch, wrong schema
version, or a required file/hash mismatch.

### `t075-retained-source-reuse-manifest-v1`

Required top-level fields, in semantic order:

```text
schema_id
a schema_version = 1
task_id = T075
approved_t075_spec_commit
planner_baseline = 95ccb6b55bc7a0214b632206ae169a533289fcf2
t065_approved_spec_commit
pinned_simulator_identity
accepted_t065_preflight
sources
validation
original_regeneration_commands
problems
```

`accepted_t065_preflight` requires exact path, persisted byte size, SHA-256, and
`passed=true`. `sources` is an array in fixed order stochastic then expert; each
entry requires exact path, byte size, SHA-256, source schema id/version, source
arm, seed range, driver seed, controller/action-space provenance, terminal and
truncation counts, shard/worker evidence, and the resolved T065 retention
manifest path/hash. `original_regeneration_commands` preserves the exact source
manifest command strings in the same stochastic/expert order.

`validation.passed` is true only if every frozen predicate passes. Otherwise the
workflow writes Case D and does not enter ownership.

### `t075-replay-group-ownership-audit-v1`

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
selection_strategy_id = leakage-safe-global-owner-v1
replay_identity = t065-replay-equivalence-key-unchanged
selection_domain = T065-source-selection-v1
group_domain = T075-replay-group-v1
parent_reuse_manifest_sha256
candidate_domain_counts
group_count
singleton_group_count
non_singleton_group_count
cross_split_group_count
excluded_non_owner_count
groups
problems
```

`candidate_domain_counts` uses fixed arm/family/split ordering. `groups` is
ascending by group digest. Each group requires: group digest, group size,
family, whether it spans splits, ordered member records, owner record or null,
and non-owner exclusion count. Every member record requires source arm,
simulator seed, source run id, source step, split, public-state identity,
selection digest, and SHA-256 of its canonical candidate bytes.

A tie described above requires `owner=null`, records all tied identities, emits
Case D, and prevents selection.

### `t075-source-selection-manifest-v1`

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
selection_strategy_id = leakage-safe-global-owner-v1
parent_reuse_manifest_sha256
parent_ownership_audit_sha256
selected_states_path
selected_states_sha256
selected_state_schema_id = t065-source-state-v1
family_order = [MAP_SCREEN, REST_ROOM, REWARDS, TREASURE_ROOM]
split_order = [train, validation, heldout]
quotas = {train:48, validation:16, heldout:16}
post_owner_available_counts
selected_counts
selected_replay_identity_digests
replay_verification
problems
```

Within each family, split order is train, validation, heldout. Within one bucket,
owners are ordered by the unchanged T065 member order key and the first frozen
quota is selected. The persisted selected-state rows remain strict
`t065-source-state-v1` rows so the merged T065 target reader can consume them
without migration. The manifest is T075-specific provenance around those
unchanged rows; it does not rewrite T065 historical selection artifacts.

`replay_verification` requires 320 attempted, 320 restored, zero replacement,
zero replay mismatch, zero selected duplicate replay key, and zero selected
cross-split replay overlap. Any short bucket or replay failure is Case D.

### `t075-retention-manifest-v1`

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
planner_baseline
terminal_case
retention_owner = T075
retention_reason
reused_artifacts
produced_artifacts
stage_commands
stage_evidence
downstream_consumers
deletion_condition
problems
```

`reused_artifacts` includes the exact accepted T065 preflight, both raw source
files and their resolved manifests, and the accepted T065 Case-D
report/retention identity. `produced_artifacts` is in stage order and records
path, persisted bytes, SHA-256, schema id/version, producer stage, and parent
artifact identities. `stage_commands` stores the exact command strings below,
including commands not executed after an early terminal case, tagged
`executed=false` when skipped.

## Retention Ownership And Deletion

From T075 implementation authorization until its terminal result is merged,
T075 is the retention owner for the two reused T065 raw source files. Retention
reason: they are the only approved source evidence from which the repaired
leakage-safe cohort may be deterministically reproduced. Immediate downstream
consumer: T075 Stage 1 ownership/selection; no other stage is allowed to scan
unselected source rows for model targets.

The raw source files may be deleted only after all of the following are true:

1. T075 has a merged terminal Case A/B/C/D report and final compact retention
   manifest;
2. no open or approved task names either raw source as a required input;
3. the Maintainer records that no pending reproduction/review needs the raw
   source;
4. for Case A/B/C, the selected 320-state artifact plus downstream compact/target
   evidence required for the accepted result is retained; for a Case D at
   ownership/selection, the raw sources remain retained until the Case-D repair
   path is explicitly closed or superseded.

T075 itself never deletes either reused raw source during execution.

## Frozen Command Contract

The implementation must support the command shapes below through the existing
neutral module `sts_combat_rl.commands.non_combat_learning`. It may add the
T075-neutral arguments/subcommand explicitly named here; it must not add a
T075-specific route to the legacy flat CLI.

The shell prefix for every WSL command is exactly:

```bash
cd /mnt/d/DeadlycatCoding/STSRL
export PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch:/mnt/d/DeadlycatCoding/STSRL/src
PY=/home/lsmft/stsrl-spikes/py313-torch/bin/python
ROOT=artifacts/t075-leakage-safe-non-combat-cohort-repair
T065=artifacts/t065-learned-non-combat-policy-v1
```

### Local/focused verification

Run from the repository root:

```bash
pytest -q tests/test_non_combat_learning.py
pytest -q
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
git diff --check
```

Focused T075 ownership tests must be added to
`tests/test_non_combat_learning.py`; no task-numbered production module is
created merely to house them.

### Stage 0 current-runtime preflight

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --retention-manifest "$ROOT/stage0-preflight.retention.json"
```

This must pass the same pinned simulator/public projection/Torch runtime boundary
as T065. The accepted T065 preflight is still validated as lineage evidence; the
fresh T075 preflight does not authorize source recollection.

### Stage 0 retained-input validation

The neutral module must expose exactly this new subcommand surface:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning validate-reuse \
  --preflight "$T065/preflight-c57b2ee-20260827.json" \
  --source "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --source "$T065/source-expert-650001-650256-deeaa46.json" \
  --output "$ROOT/stage0-retained-source-reuse.json" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/stage0-retained-source-reuse.retention.json"
```

`validate-reuse` performs the exact path/size/hash/manifest-resolution/source
schema/provenance checks above using bounded-memory/streaming validation. It
never creates a simulator source run.

### Stage 1 selection only

The neutral `select` subcommand must accept the explicit strategy and audit paths
shown here:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning select \
  --selection-strategy leakage-safe-global-owner-v1 \
  --input "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --input "$T065/source-expert-650001-650256-deeaa46.json" \
  --reuse-manifest "$ROOT/stage0-retained-source-reuse.json" \
  --ownership-audit "$ROOT/stage1-replay-group-ownership-audit.json" \
  --output "$ROOT/stage1-selected-states.json" \
  --manifest "$ROOT/stage1-selection-manifest.json" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage0-retained-source-reuse.retention.json" \
  --retention-manifest "$ROOT/stage1-selection.retention.json"
```

No `collect` command may be executed in T075. A command log containing a T075
source `collect` invocation is itself an acceptance failure.

Stage 1 performs no simulator worker collection. Replay verification of selected
states may use bounded parallelism, but persisted owner/selection order is
independent of completion order.

### Stage 2 all-action counterfactual targets

Only after a valid 320-state Stage 1 result:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning target \
  --states "$ROOT/stage1-selected-states.json" \
  --output "$ROOT/stage2-target-table.json" \
  --sim-seed 1 --ascension 20 \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage1-selection.retention.json" \
  --retention-manifest "$ROOT/stage2-target-table.retention.json"
```

For exactly 320 selected states, the command must use the frozen T065 topology:
16 shards, 20 selected states per shard, and at most 16 concurrent simulator
workers. Each shard owns every eligible action and every continuation seed for
its 20 states. The manifest must report all 16 shard ranges and worker count.

### Stage 4 two-seed Torch training

Stage 3 is the strict target/model-input validation performed before this
command. Training command:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage2-target-table.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/stage4-training.retention.json"
```

Exactly model seeds 653001 and 653002 run, each 1500 optimizer steps and
`torch_threads=1`. They may execute concurrently as exactly two isolated model
processes; no additional model seed is allowed.

### Stage 5 held-out gate

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --sim-seed 1 --ascension 20 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/stage5.retention.json"
```

Without `--run-stage6`, a valid failed Stage 5 writes terminal Case C. A valid
passed Stage 5 writes the frozen Stage 5 report and returns the existing
non-success/incomplete `decision_pending` status; that status is the only
condition under which the Stage 6 command below may be launched. It is not an
error to repair by changing thresholds.

### Conditional Stage 6

Run iff the frozen Stage 5 report passes:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage6-complete-run-report.json" \
  --run-stage6 --sim-seed 1 --ascension 20 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --preceding-manifest "$ROOT/stage5.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/stage6.retention.json"
```

Stage 6 must use exactly three arms x 16 shards x 16 simulator seeds, seeds
651001..651256 in every arm, at most 16 concurrent simulator workers, driver /
fallback seed 654002, and exactly 768 terminal runs for a valid complete report.
The stage manifest must enumerate all 48 arm/shard ranges and actual worker
count.

### Final retention manifest

Every terminal Case A/B/C/D writes:

```text
artifacts/t075-leakage-safe-non-combat-cohort-repair/terminal-decision-report.json
artifacts/t075-leakage-safe-non-combat-cohort-repair/t075-retention-manifest.json
```

using the schemas above. Early Case D records completed preceding artifacts,
failed current artifacts separately, all skipped downstream commands as
`executed=false`, and exactly one narrow repair recommendation.

## Compatibility With T065 Downstream Readers

T075 changes cohort ownership only. The selected-state file uses unchanged
`t065-source-state-v1` rows, model input stays `non-combat-model-input-v1`, Stage
2 target rows retain the T065 counterfactual-target schema, checkpoints retain
the T065 ranker checkpoint schema, and Stage 5/6 reducer semantics remain T065.

The T075-specific reuse/ownership/selection/retention manifests add parent
provenance around those existing scientific rows. They may not require changes
to accepted T065 historical artifacts or weaken current strict readers. Any
needed reader extension must be additive and explicitly discriminate the T075
selection strategy; silently treating the T075 strategy as historical T065
selection is forbidden.

## Lifecycle

T075 remains `DRAFT` and `implementation_authorized=false` until a Main
Maintainer exact-head `SPEC APPROVED` comment. T065 remains `DONE`; T066 remains
`DRAFT`; no successor is authorized by this specification.
