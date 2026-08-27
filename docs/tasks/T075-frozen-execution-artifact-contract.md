# T075 Normative Execution, Reuse, And Artifact Contract

This file is a normative part of T075 together with
[`T075-leakage-safe-non-combat-cohort-repair.md`](T075-leakage-safe-non-combat-cohort-repair.md).
It freezes execution checkout/runtime, retained inputs, path normalization,
commands, sharding, artifact schemas, ordering, retention, and failure rules.
If the primary task document is less specific on these details, this file
controls. Material changes after exact-head approval require Maintainer
re-approval. This file does not authorize implementation by itself.

## 1. Code Checkout And Stable Artifact Roots

All scientific execution uses this isolated task worktree:

```text
CODE_WINDOWS = D:\DeadlycatCoding\STSRL\.claude\worktrees\t075-leakage-safe-non-combat-cohort-repair
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
BRANCH = task/T075-leakage-safe-non-combat-cohort-repair
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE_PYTHONPATH = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
PROJECT_PYTHONPATH = ${CODE}/src
```

Stable artifacts remain outside the disposable task worktree:

```text
STABLE_ROOT = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE_ROOT}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE_ROOT}/t065-learned-non-combat-policy-v1
```

Every scientific command runs from `CODE` with:

```bash
cd "$CODE"
export PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch:$CODE/src
```

No project import may resolve from `/mnt/d/DeadlycatCoding/STSRL/src`.

Before each scientific stage, require and record:

```bash
test "$(git branch --show-current)" = "task/T075-leakage-safe-non-combat-cohort-repair"
test -z "$(git status --porcelain)"
APPROVED_SPEC={APPROVED_T075_SPEC_COMMIT}
git merge-base --is-ancestor "$APPROVED_SPEC" HEAD
CODE_HEAD=$(git rev-parse HEAD)
```

`{APPROVED_T075_SPEC_COMMIT}` is replaced only by the exact commit named in the
Maintainer `SPEC APPROVED` comment. Implementation may advance `HEAD` on this
same branch after approval, but every executed stage records its exact
`CODE_HEAD`. Branch switching is forbidden. Wrong branch, dirty checkout, or an
approved spec that is not an ancestor of `HEAD` is Case D before the affected
stage.

## 2. Frozen Output Paths

All T075 outputs are below `ROOT` with these exact names:

```text
stage0-preflight.json
stage0-preflight.retention.json
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

Temporary shard files may exist only in stage-local temporary directories below
`ROOT`. A successful stage removes them; a failed stage either removes them or
records them explicitly as retained failed-stage evidence.

## 3. Exact Retained T065 Inputs

The two scientific source inputs are fixed and must not be regenerated:

| Arm | Repository-relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Accepted T065 lineage evidence is exactly:

```text
preflight_path = artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.json
preflight_sha256 = a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334

case_d_decision_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json
case_d_decision_bytes = 198842
case_d_decision_sha256 = 0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc

case_d_retention_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.retention.json
case_d_retention_bytes = 36186
case_d_retention_sha256 = fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf
```

The `deeaa46-retry2` decision/retention files are not the accepted final Case-D
identities and cannot satisfy this contract.

The approved T065 specification identity is exactly:

`a13c92a66b4ad25a7b0bdc8097cc0cfdc26dffa`

### Path normalization

For all retained-manifest path comparisons, canonicalize to repository-relative
POSIX paths:

1. replace backslashes with `/`;
2. strip exactly one of these prefixes when present:
   - `D:/DeadlycatCoding/STSRL/`
   - `/mnt/d/DeadlycatCoding/STSRL/`;
3. strip one leading `./` if present;
4. collapse `.` components and reject any `..` component;
5. require the result to start with `artifacts/`;
6. compare the resulting case-sensitive string exactly to the paths frozen here.

Paths outside the stable repository root or basename-only matches are invalid.

### Source retention-manifest resolution

For each raw source, inspect only `*.retention.json` files directly in `T065`.
A manifest matches only if it records, after path normalization:

- the exact raw-source path, byte size, and SHA-256 above;
- the matching source arm;
- approved T065 spec exactly `a13c92a66b4ad25a7b0bdc8097cc0cfdc26dffa`;
- source seeds exactly `650001..650256` and driver seed `654001`;
- pinned simulator identity;
- battle controller `oracle_search_v1_highest_mean_s20`;
- exact `ActionSpaceConfig.initial_no_potions()` identity;
- 16 source shards and 16 effective workers;
- 256 requested/terminal runs and zero truncations.

Exactly one matching retention manifest is required per raw source. Zero or more
than one is Case D at `source-input-reuse`. Copy the original source-regeneration
command strings from the matched manifests into T075 provenance, but never
execute them in T075.

## 4. Candidate Domain And Ownership Identity

Ownership admits only rows that:

- pass the strict current `t065-source-state-v1` reader;
- have source-run `terminal == true`;
- belong to exactly `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, or `TREASURE_ROOM`;
- retain the frozen simulator-seed split;
- pass all existing T065 public/model/action/replay/provenance checks.

Nonterminal/truncated rows remain auditable evidence but cannot become owners or
selected states. Malformed/provenance-invalid rows are Case D, not ordinary
exclusions.

The replay-equivalence key remains unchanged:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON for T075 digests is UTF-8 with sorted keys, separators
`(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, and no trailing newline in
the bytes used for a digest.

Group identity is:

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_payload = {
  "family": family,
  "public_state_identity": public_state_identity,
  "ordered_legal_action_identities": ordered existing JSON-safe identity mappings
}
group_digest = sha256(T075_GROUP_DOMAIN + canonical_json(group_payload)).hexdigest()
```

Groups serialize ascending by `group_digest`.

Member order reuses T065 exactly:

```text
selection_digest = sha256(
  b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

If two distinct source rows in one replay group have an identical full
`member_order_key`, T075 is Case D at `cohort-ownership`. Report all tied rows'
source arm, simulator seed, source run id, source step, split,
public-state identity, and group digest. Do not introduce another tie-break field.

Otherwise the first member is the unique owner. All non-owners are excluded
before quota selection, and the owner keeps the split implied by its simulator
seed.

Selection strategy id:

`leakage-safe-global-owner-v1`

## 5. Artifact Schemas

Every schema below has `schema_version = 1`. Required fields cannot be omitted or
silently defaulted. Unknown additive fields are allowed only when they do not
change interpretation. Missing required fields, wrong ordering/version, invalid
parent identities, non-finite numeric values, or required file/hash mismatch fail
closed.

### 5.1 `t075-retained-source-reuse-manifest-v1`

Required top-level fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
planner_baseline = 95ccb6b55bc7a0214b632206ae169a533289fcf2
code_head
pinned_simulator_identity
accepted_t065_preflight
accepted_t065_case_d
sources
validation
original_regeneration_commands
problems
```

`sources` order is stochastic then expert. Each entry records normalized path,
absolute stable path, bytes, SHA-256, schema/version, arm, seed range, driver
seed, controller/action-space provenance, terminal/truncation counts,
shard/worker evidence, resolved retention-manifest normalized/absolute path and
SHA-256, and compatibility status.

### 5.2 `t075-replay-group-ownership-audit-v1`

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
code_head
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
group_counts_by_family
group_counts_by_split
group_size_histogram
owner_counts_by_family_split
groups
problems
```

Ordering/semantics:

- `candidate_domain_counts`: arm stochastic/expert, then family
  MAP/REST/REWARDS/TREASURE, then split train/validation/heldout; each row records
  raw, terminal, nonterminal-excluded, unsupported-family-excluded, and
  valid-terminal counts;
- `group_counts_by_family`: four rows in frozen family order, each with total,
  singleton, non-singleton, cross-split, and non-owner-excluded counts;
- `group_counts_by_split`: train/validation/heldout rows; each has
  `present_group_count` (group has any member in split), `owner_group_count`
  (owner lies in split), and `cross_split_present_group_count`;
- `group_size_histogram`: ascending integer `group_size`, each with `group_count`;
  histogram counts sum to `group_count`;
- `owner_counts_by_family_split`: 12 family-major/split-minor rows with surviving
  owner count before quota selection.

`groups` is ascending by group digest. Each group records digest, family, size,
splits represented in frozen split order, cross-split flag, ordered members,
owner or null, and exclusion count. Each member records arm, seed, run id, source
step, split, public-state identity, selection digest, and canonical-candidate
SHA-256. An exact member-order tie requires `owner=null` and Case D.

### 5.3 `t075-source-selection-manifest-v1`

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
approved_t075_spec_commit
code_head
selection_strategy_id = leakage-safe-global-owner-v1
parent_reuse_manifest_sha256
parent_ownership_audit_sha256
selected_states_path
selected_states_sha256
selected_state_schema_id = t065-source-state-v1
selected_state_file_format = t065-source-state-jsonl-v1
family_order = [MAP_SCREEN, REST_ROOM, REWARDS, TREASURE_ROOM]
split_order = [train, validation, heldout]
quotas = {train:48, validation:16, heldout:16}
post_owner_available_counts
selected_counts
selected_replay_identity_digests
replay_verification
problems
```

`stage1-selected-states.json` uses the current T065 JSONL row format: UTF-8,
exactly one complete `t065-source-state-v1` JSON object per line, no wrapper
array/object, selected-state indices ordered `0..319`, and one newline after each
row including the final row. The strict current T065 reader must round-trip all
320 rows.

`post_owner_available_counts` and `selected_counts` are family-major then
split-minor. `replay_verification` includes the Stage 1 shard/worker evidence
below and requires 320 attempted/restored, zero mismatch, zero replacement, zero
selected replay duplicate, and zero selected cross-split replay overlap.

### 5.4 `t075-retention-manifest-v1`

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

`produced_artifacts` is stage ordered. Each item records normalized and absolute
stable path, bytes, SHA-256, schema id/version, producer stage, code head, and
ordered parent identities.

`stage_commands` has exactly one entry for each logical stage in this order:

```text
stage0-preflight
stage0-reuse
stage1-selection-replay
stage2-target
stage4-train
stage5-gate
stage6-eval
terminal-finalize
```

Each entry requires:

```text
stage
exact_command
status = executed | skipped
skip_reason = string | null
code_head
started_at = timestamp | null
finished_at = timestamp | null
exit_code = integer | null
terminal_status = passed | failed | case_d | skipped
wall_clock_seconds = finite number | null
shard_count = integer | null
requested_worker_count = integer | null
actual_worker_count = integer | null
ranges = ordered array
parent_artifact_identities = ordered array
output_artifact_identities = ordered array
```

Skipped stages have null execution fields, explicit `skip_reason`, and empty
outputs.

`stage_evidence` uses the same stage order. Each entry requires:

```text
stage
executed = bool
terminal_status
code_head
shard_count
requested_worker_count
actual_worker_count
ranges
return_status_by_shard
wall_clock_seconds
parent_artifact_identities
output_artifact_identities
counts
problems
```

For non-sharded stages, shard/worker/range fields are null/empty. Skipped stages
have `executed=false`, `terminal_status=skipped`, and no runtime outputs.

## 6. Stage 1 Replay Verification

After deterministic ownership/quota selection assigns indices `0..319`, replay
verification is exactly 16 contiguous shards of 20 indices:

```text
00: 000..019    08: 160..179
01: 020..039    09: 180..199
02: 040..059    10: 200..219
03: 060..079    11: 220..239
04: 080..099    12: 240..259
05: 100..119    13: 260..279
06: 120..139    14: 280..299
07: 140..159    15: 300..319
```

Requested and target actual worker count is exactly 16, with no more than 16
concurrent simulator workers. If the runtime cannot establish the frozen
16-worker plan, stop before replay and record Case D rather than silently using a
substantial single-worker path.

The Stage 1 manifest/evidence records shard ranges, requested/actual workers,
per-shard return status, attempted/restored/mismatch counts, wall-clock, code
head, parent identities, and output identities.

## 7. Frozen Command Templates

The implementation may add only the neutral arguments/subcommands named below to
`sts_combat_rl.commands.non_combat_learning`; no T075 route may be added to the
legacy flat CLI.

Common prefix:

```bash
CODE=/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
STABLE=/mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT=$STABLE/t075-leakage-safe-non-combat-cohort-repair
T065=$STABLE/t065-learned-non-combat-policy-v1
PY=/home/lsmft/stsrl-spikes/py313-torch/bin/python
cd "$CODE"
export PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch:$CODE/src
```

### Local/focused gates

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

### Stage 0 preflight

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --retention-manifest "$ROOT/stage0-preflight.retention.json"
```

### Stage 0 retained-input validation

Neutral subcommand `validate-reuse`:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning validate-reuse \
  --source "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --source "$T065/source-expert-650001-650256-deeaa46.json" \
  --accepted-preflight "$T065/preflight-c57b2ee-20260827.json" \
  --accepted-case-d "$T065/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json" \
  --accepted-case-d-retention "$T065/source-selection-650001-650256-a69972f.retention.json" \
  --output "$ROOT/stage0-retained-source-reuse.json" \
  --retention-manifest "$ROOT/stage0-retained-source-reuse.retention.json"
```

This validates exact hashes/sizes, path normalization, retention-manifest
resolution, source provenance, and accepted final T065 Case-D lineage. It never
runs source collection.

### Stage 1 ownership/selection/replay

```bash
$PY -m sts_combat_rl.commands.non_combat_learning select \
  --input "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --input "$T065/source-expert-650001-650256-deeaa46.json" \
  --selection-strategy leakage-safe-global-owner-v1 \
  --reuse-manifest "$ROOT/stage0-retained-source-reuse.json" \
  --output "$ROOT/stage1-selected-states.json" \
  --ownership-audit "$ROOT/stage1-replay-group-ownership-audit.json" \
  --manifest "$ROOT/stage1-selection-manifest.json" \
  --replay-verify --replay-shard-count 16 --replay-worker-count 16 \
  --retention-manifest "$ROOT/stage1-selection.retention.json"
```

No `collect` invocation is permitted in T075.

### Stage 2 targets

Only after valid Stage 1:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning target \
  --states "$ROOT/stage1-selected-states.json" \
  --output "$ROOT/stage2-target-table.json" \
  --shard-count 16 --worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage1-selection.retention.json" \
  --retention-manifest "$ROOT/stage2-target-table.retention.json"
```

Stage 2 uses the same 16 contiguous 20-index shard ranges as Stage 1 and owns all
eligible actions/continuation seeds for each assigned state.

### Stage 4 training

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage2-target-table.retention.json" \
  --retention-manifest "$ROOT/stage4-training.retention.json"
```

Exactly model seeds 653001/653002 are trained; the two processes may run
concurrently and each uses `torch_threads=1`.

### Stage 5 held-out gate

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --retention-manifest "$ROOT/stage5.retention.json"
```

A valid Stage 5 failure is Case C and skips Stage 6.

### Conditional Stage 6

Only if the persisted Stage 5 report passes:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --stage5-report "$ROOT/stage5-heldout-report.json" \
  --output "$ROOT/stage6-complete-run-report.json" \
  --run-stage6 --stage6-shard-count 16 --stage6-worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage5.retention.json" \
  --retention-manifest "$ROOT/stage6.retention.json"
```

Stage 6 remains exactly three matched arms x 16 shards x 16 seeds, with at most
16 concurrent simulator workers, seeds `651001..651256`, and 768 valid terminal
runs for a valid complete stage.

### Terminal finalization

Neutral subcommand `finalize` produces the terminal decision and final retention
manifest without rerunning science:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json"
```

## 8. Retention And Deletion

From implementation authorization until the terminal result is merged, T075 is
the retention owner for the two reused raw sources. Reason: they are the unique
approved source evidence for deterministic repaired cohort construction.
Immediate downstream consumer: T075 Stage 1; later stages may not scan unselected
source rows for model/target decisions.

Raw sources may be deleted only when all conditions hold:

1. T075 has a merged terminal Case A/B/C/D and compact final retention manifest;
2. no open/approved task names either raw source as required input;
3. Maintainer records that no pending reproduction/review needs them;
4. for Case A/B/C, selected 320-state and accepted downstream evidence are
   retained; for Case D at ownership/selection, raw sources remain until that
   repair route is explicitly closed or superseded.

T075 never deletes these raw sources during execution.

## 9. Failure And Reporting Contract

Case D includes any retained-input mismatch/ambiguity, path-normalization failure,
wrong/dirty code checkout, approved-spec ancestry failure, exact owner-key tie,
insufficient owner bucket, selected replay failure, target incompleteness,
schema/hidden-field failure, simulator/provenance mismatch, or forbidden
truncation. Do not recollect sources or tune ownership to recover inside T075.

The implementation report must include exact approved spec; exact code head per
stage; normalized/absolute reused input identities; ownership counts by family,
split, and group size; post-owner availability and selected counts; exact Stage
1 replay shard/worker/return/wall-clock evidence; all reached stage commands and
evidence; artifact hashes/sizes/parents; full/focused verification; costs;
exactly one terminal Case A/B/C/D; and exactly one next recommendation.
