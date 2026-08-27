# T075 Normative Execution, Reuse, And Artifact Contract

This file is normative together with [`T075-leakage-safe-non-combat-cohort-repair.md`](T075-leakage-safe-non-combat-cohort-repair.md). It freezes the execution checkout/runtime, retained inputs, path normalization, commands, sharding, artifact schemas, ordering, retention, and failure rules. Material changes after exact-head approval require Maintainer re-approval.

## Code Checkout And Artifact Roots

Scientific execution uses exactly this isolated worktree:

```text
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
BRANCH = task/T075-leakage-safe-non-combat-cohort-repair
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
```

Stable artifacts remain outside the disposable task worktree:

```text
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

Every scientific command runs from `CODE` with `PYTHONPATH=${NATIVE}:${CODE}/src`; imports from `/mnt/d/DeadlycatCoding/STSRL/src` are forbidden.

Before every scientific stage:

```bash
cd "$CODE"
test "$(git branch --show-current)" = "task/T075-leakage-safe-non-combat-cohort-repair"
test -z "$(git status --porcelain)"
APPROVED_SPEC={APPROVED_T075_SPEC_COMMIT}
git merge-base --is-ancestor "$APPROVED_SPEC" HEAD
CODE_HEAD=$(git rev-parse HEAD)
```

The placeholder is replaced only by the exact Maintainer-approved T075 spec commit. Implementation may advance `HEAD` on the same branch, but every executed stage records its exact `CODE_HEAD`. Branch switching is forbidden. Wrong branch, dirty checkout, or failed approved-spec ancestry is Case D before that stage.

## Frozen Output Paths

All produced artifacts live below `ROOT` with these exact names:

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

## Exact Retained T065 Inputs

Approved T065 specification, confirmed by PR #74 `SPEC APPROVED` and current main:

`a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`

Required raw source inputs, never recollected by T075:

| Arm | Repository-relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Accepted lineage evidence:

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

The older `deeaa46-retry2` decision/retention files are explicitly not accepted final T065 Case-D evidence.

### Path normalization

For retained-manifest path comparisons, normalize to repository-relative POSIX paths:

1. replace backslashes with `/`;
2. strip one exact prefix if present: `D:/DeadlycatCoding/STSRL/` or `/mnt/d/DeadlycatCoding/STSRL/`;
3. strip one leading `./`;
4. collapse `.` and reject any `..` component;
5. require prefix `artifacts/`;
6. compare the case-sensitive normalized string exactly.

No basename-only comparison is valid.

### Source retention-manifest resolution

For each raw source, inspect only `*.retention.json` directly under `T065`. Exactly one manifest must match all of:

- normalized raw path, exact byte size, and exact SHA-256 above;
- matching source arm;
- approved T065 spec exactly `a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`;
- source seeds `650001..650256`, driver seed `654001`;
- pinned simulator identity;
- battle controller `oracle_search_v1_highest_mean_s20`;
- exact `ActionSpaceConfig.initial_no_potions()` identity;
- 16 source shards, 16 effective workers;
- 256 requested/terminal runs and zero truncations.

Zero or multiple matches are Case D at `source-input-reuse`. Preserve matched manifests' original regeneration commands as provenance text only; T075 never executes them.

## Candidate Domain And Ownership

Ownership admits only strict-reader-valid `t065-source-state-v1` rows whose source run has `terminal == true`, whose family is exactly one of `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`, whose simulator seed maps to the frozen T065 split, and whose existing public/model/action/replay/provenance checks pass. Nonterminal/truncated rows remain audited evidence but are never owners/selectable. Malformed/provenance-invalid rows are Case D.

Replay-equivalence key remains exactly:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON uses UTF-8, sorted keys, separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, with no newline in digest bytes.

Replay-group identity:

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_payload = {
  "family": family,
  "public_state_identity": public_state_identity,
  "ordered_legal_action_identities": ordered JSON-safe identity mappings
}
group_digest = sha256(T075_GROUP_DOMAIN + canonical_json(group_payload)).hexdigest()
```

Groups serialize ascending by `group_digest`.

Member order remains T065:

```text
selection_digest = sha256(
  b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

If distinct rows tie on the full pair, Case D at `cohort-ownership`; report all tied source arm/seed/run/step/split/public-state/group identities and do not add a tie-break field. Otherwise the first member is the sole owner and keeps its simulator-seed split. All non-owners are excluded before quota selection.

Selection strategy id: `leakage-safe-global-owner-v1`.

## Artifact Schemas

Every schema below has `schema_version = 1`. Missing required fields, wrong version/order, non-finite values, parent mismatch, or required file/hash mismatch fails closed.

### `t075-retained-source-reuse-manifest-v1`

Required fields:

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

`sources` is ordered stochastic then expert. Each entry records normalized and absolute stable paths, bytes, SHA-256, schema/version, arm, seeds, driver seed, controller/action-space provenance, terminal/truncation counts, shard/worker evidence, matched retention-manifest path/hash, and compatibility status.

### `t075-replay-group-ownership-audit-v1`

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

Ordering and definitions:

- `candidate_domain_counts`: arm stochastic/expert, family MAP/REST/REWARDS/TREASURE, split train/validation/heldout; each row contains raw, terminal, nonterminal-excluded, unsupported-family-excluded, and valid-terminal counts;
- `group_counts_by_family`: frozen family order; total, singleton, non-singleton, cross-split, and non-owner-excluded counts;
- `group_counts_by_split`: frozen split order; `present_group_count` counts each group once when the split has any member, `owner_group_count` counts owner split, and `cross_split_present_group_count` counts cross-split groups present there;
- `group_size_histogram`: ascending integer group size and group count, summing to total group count;
- `owner_counts_by_family_split`: 12 family-major/split-minor owner counts before quota selection.

`groups` is ascending by group digest and records family, size, represented splits, cross-split flag, ordered members, owner or null, and exclusion count. Members record arm, seed, run, step, split, public-state identity, selection digest, and canonical-candidate SHA-256. Exact member-order ties use `owner=null` and Case D.

### `t075-source-selection-manifest-v1`

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

`stage1-selected-states.json` is the current T065 JSONL row format: UTF-8, one complete `t065-source-state-v1` JSON object per line, no wrapper array/object, selected indices `0..319` in order, one newline after every row including the last, and strict-reader round-trip for all 320 rows.

`replay_verification` records the exact Stage 1 shard/worker evidence below and requires 320 attempted/restored, zero mismatch/replacement, zero selected replay duplicate, and zero selected cross-split replay overlap.

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

`produced_artifacts` is stage ordered; each entry records normalized/absolute path, bytes, SHA-256, schema/version, producer stage, code head, and ordered parent identities.

`stage_commands` has one entry, in order, for `stage0-preflight`, `stage0-reuse`, `stage1-selection-replay`, `stage2-target`, `stage4-train`, `stage5-gate`, `stage6-eval`, `terminal-finalize`. Each entry requires:

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

Skipped entries have null runtime fields, explicit skip reason, and empty outputs.

`stage_evidence` uses the same stage order and requires:

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

Non-sharded stages use null/empty shard fields. Skipped stages have `executed=false`, `terminal_status=skipped`, and no runtime outputs.

## Stage 1 Replay Sharding

After owner/quota selection assigns indices `0..319`, replay verification is exactly 16 contiguous shards, 20 indices each:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested and required actual worker count is 16, with at most 16 concurrent simulator workers. If that plan cannot be established, stop before replay and record Case D rather than silently degrading to a substantial single-worker run. Record ranges, requested/actual workers, per-shard return status, attempted/restored/mismatch counts, total wall-clock, code head, parent and output identities.

## Frozen Command Templates

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

Local/focused gates:

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

Stage 0 preflight:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --retention-manifest "$ROOT/stage0-preflight.retention.json"
```

Neutral `validate-reuse`:

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

Stage 1 selection/replay:

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

Stage 2 targets, only after valid Stage 1:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning target \
  --states "$ROOT/stage1-selected-states.json" \
  --output "$ROOT/stage2-target-table.json" \
  --shard-count 16 --worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage1-selection.retention.json" \
  --retention-manifest "$ROOT/stage2-target-table.retention.json"
```

Stage 2 uses the same 16 x 20 contiguous selected-index ranges and all frozen continuation actions/seeds.

Stage 4 training:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage2-target-table.retention.json" \
  --retention-manifest "$ROOT/stage4-training.retention.json"
```

Exactly model seeds 653001/653002 are trained; two processes may run concurrently, each with `torch_threads=1`.

Stage 5:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --retention-manifest "$ROOT/stage5.retention.json"
```

Valid Stage 5 failure is Case C and skips Stage 6.

Conditional Stage 6:

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

Stage 6 remains three matched arms x 16 shards x 16 seeds, seeds `651001..651256`, at most 16 concurrent simulator workers, 768 terminal runs for a valid complete stage.

Neutral terminal finalization:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json"
```

## Retention And Failure Rules

T075 owns retention of both raw T065 sources from implementation authorization until its terminal result merges. They are retained because they are the unique approved source evidence for deterministic repaired cohort construction. They may be deleted only after: a merged terminal T075 report/compact retention manifest; no open/approved task still requires them; Maintainer records no pending reproduction need; and accepted compact downstream evidence is retained. For Case D at ownership/selection, retain raw sources until that repair route is explicitly closed or superseded. T075 never deletes them during execution.

Case D includes retained-input mismatch/ambiguity, path-normalization failure, wrong/dirty checkout, approved-spec ancestry failure, exact owner-key tie, insufficient owner bucket, selected replay failure, target incompleteness, schema/hidden-field failure, simulator/provenance mismatch, or forbidden truncation. T075 may not recollect sources or tune ownership to recover.

The implementation report must include exact approved spec, exact code head per stage, normalized/absolute input identities, ownership counts by family/split/group size, post-owner and selected counts, Stage 1 replay shard/worker/return/wall-clock evidence, reached stage commands/evidence, artifact hashes/sizes/parents, full/focused verification, costs, exactly one terminal Case A/B/C/D, and exactly one next recommendation.
