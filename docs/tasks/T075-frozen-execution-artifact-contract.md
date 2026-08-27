# T075 Normative Execution, Reuse, And Artifact Contract

This file is normative together with [`T075-leakage-safe-non-combat-cohort-repair.md`](T075-leakage-safe-non-combat-cohort-repair.md). It freezes the execution checkout/runtime, retained-input resolver, path normalization, commands, sharding, Stage-3 placement, artifact schemas, parent identities, terminal materialization, retention, and failure semantics. Material changes after exact-head approval require Maintainer re-approval.

## Frozen constants

```text
PLANNER_BASELINE = 95ccb6b55bc7a0214b632206ae169a533289fcf2
T065_APPROVED_SPEC = a13c92a66b4d9ad9f6a730293cadc8d66b4a699c
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
BRANCH = task/T075-leakage-safe-non-combat-cohort-repair
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

Every scientific command runs from `CODE` with `PYTHONPATH=${NATIVE}:${CODE}/src`. Importing project code from `/mnt/d/DeadlycatCoding/STSRL/src` is forbidden.

Before each scientific execution stage:

```bash
cd "$CODE"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain)"
APPROVED_SPEC={APPROVED_T075_SPEC_COMMIT}
git merge-base --is-ancestor "$APPROVED_SPEC" HEAD
CODE_HEAD=$(git rev-parse HEAD)
```

The placeholder is replaced only with the exact Maintainer-approved T075 spec commit. Each stage records its exact `CODE_HEAD`. Branch switching is forbidden.

## Frozen outputs

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
stage2-target-validation.json
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

`terminal-decision-report.json` is the only authoritative T075 terminal-decision path. Per-command `*.t065-terminal-decision-report.json` files are forbidden.

## Retained T065 source identities

T075 reuses and never recollects:

| Arm | Relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Accepted T065 lineage:

```text
accepted_preflight_content_sha256 = a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334
case_d_decision_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json
case_d_decision_bytes = 198842
case_d_decision_sha256 = 0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc
case_d_retention_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.retention.json
case_d_retention_bytes = 36186
case_d_retention_sha256 = fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf
```

The older `deeaa46-retry2` decision/retention files are not accepted final lineage.

### Path normalization

All identity comparisons use repository-relative POSIX paths. Replace `\\` with `/`; strip one exact stable-root prefix (`D:/DeadlycatCoding/STSRL/` or `/mnt/d/DeadlycatCoding/STSRL/`) when present; strip one leading `./`; collapse `.`; reject `..`; require prefix `artifacts/`; then compare case-sensitively. Basename-only matching is invalid.

### Accepted historical preflight aliases

Exactly these source-specific pairs are accepted:

| Arm | Raw alias | Retention alias |
|---|---|---|
| stochastic | `artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.json` | `artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.retention.json` |
| expert | `artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.json` | `artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.retention.json` |

Each raw alias must hash to `a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334`, parse as the accepted T065 preflight schema/version, record `T065_APPROVED_SPEC`, and match the pinned simulator/controller/action-space identity. The paired retention alias must parse, reference that raw alias, and be internally compatible. T075 computes and records each retention alias's actual full SHA-256 rather than inferring it from review-comment prefixes.

## Exact two-level source-retention resolver

The resolver does not recursively search lineage graphs.

For each frozen raw source independently:

1. Enumerate only direct `T065/*.retention.json` files in normalized-path order.
2. Strict-read candidate roots as `t065-retention-manifest-v1`, version `1`, `task_id="T065"`, `approved_spec_commit == T065_APPROVED_SPEC`, with mappings/lists required by the existing strict T065 retention reader.
3. A root becomes a candidate only when `artifacts[]` contains exactly one entry with `role == "current_output"` whose normalized `path`, `size_bytes`, and `sha256` equal the frozen raw source. References under `preceding_stage_manifests` never count as matches. Thus the final Case-D retention manifest cannot falsely match merely because it references both source manifests.
4. Exactly one root candidate must remain. Zero or multiple candidates are Case D at `source-input-reuse`.
5. The candidate must contain `stage_evidence["stage1-source-collection"]` with `stage == "stage1-source-collection"`, `status == "completed"`, `terminal is false`, `artifact_roles` containing `current_output`, and `preceding_stage_manifests["stage0_preflight"]` equal to the arm-specific accepted preflight-retention descriptor after path/hash/size validation.
6. The candidate's `regeneration_commands` must contain exactly one non-empty command and that string must equal `stage_evidence["stage1-source-collection"]["command"]`. The command is retained as provenance and is not parsed to infer scientific counts.
7. Candidate top-level `frozen_config` must equal the frozen current `T065ExperimentConfig().to_dict()` and top-level `simulator_identity` must equal `lightspeed_source_identity_dict()`.
8. Remaining scientific predicates are proved from the raw source JSON metadata. Exact required top-level fields are:
   - `schema_id == "t065-learned-non-combat-policy-v1"`, `schema_version == 1`;
   - `approved_spec_commit == T065_APPROVED_SPEC`;
   - `frozen_config == T065ExperimentConfig().to_dict()`;
   - `arm` equals expected arm;
   - `driver_seed == 654001`;
   - `requested_seed_count == 256`, `terminal_run_count == 256`, `truncated_run_count == 0`, `failed_run_count == 0`;
   - `selected_candidate_count == len(records)`, `problems == []`;
   - `worker_count == 16`, `shard_count == 16`;
   - `action_space == frozen_action_space().to_dict()`;
   - `battle_controller_provenance == frozen_battle_provenance()` and its name is `oracle_search_v1_highest_mean_s20`;
   - `simulator_identity == lightspeed_source_identity_dict()`;
   - `run_summaries` has exactly 256 problem-free terminal entries for seeds `650001..650256`, with matching `source_arm` and `source_run_id == f"{arm}:{seed}"`.
9. Raw `shard_specs` has exactly 16 ordered entries. For `i=0..15`: `shard_index=i`, `seed_start=650001+16*i`, `seed_end=650016+16*i`, `seed_count=16`, `worker_count=16`, `requested_seed_count=16`, `terminal_run_count=16`, `truncated_run_count=0`, `failed_run_count=0`, and empty `problems`.
10. Preserve in T075 reuse evidence: source manifest path/hash, `current_output` identity, raw source path/hash/size, raw metadata validation result, exact Stage-1 evidence, top-level config/simulator identity, referenced preflight raw/retention paths and full hashes, and original regeneration command.

Any mismatch is Case D at `source-input-reuse`.

## Candidate domain and global ownership

Selectable candidates must pass the strict `t065-source-state-v1` reader, come from a source run with `terminal == true`, belong to exactly `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, or `TREASURE_ROOM`, retain the frozen seed split, and pass existing T065 public/model/action/replay/provenance checks. Nonterminal/truncated rows remain auditable but never selectable.

Replay equivalence remains:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON is UTF-8, sorted keys, separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, with no digest newline.

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_digest = sha256(T075_GROUP_DOMAIN + canonical_json({
  "family": family,
  "public_state_identity": public_state_identity,
  "ordered_legal_action_identities": ordered_legal_action_identities
})).hexdigest()
```

Member order remains exactly T065:

```text
selection_digest = sha256(
  b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Exact full-key ties between distinct source rows are Case D. Otherwise first member is the sole owner and keeps its simulator-seed split. Non-owners are excluded before the unchanged 48/16/16 quotas. Strategy id is `leakage-safe-global-owner-v1`.

## T075 artifact schemas

All have `schema_version=1`; required-field, version, ordering, parent, non-finite, or hash mismatch fails closed.

### `t075-retained-source-reuse-manifest-v1`

Required: `schema_id`, `schema_version`, `task_id`, `approved_t075_spec_commit`, `planner_baseline`, `code_head`, `pinned_simulator_identity`, `accepted_t065_preflight_content_sha256`, `accepted_t065_case_d`, ordered `sources`, `validation`, `original_regeneration_commands`, `problems`.

Each source entry records every resolver identity/evidence item listed above. Source order is stochastic then expert.

### `t075-replay-group-ownership-audit-v1`

Required: `schema_id`, `schema_version`, `task_id`, `approved_t075_spec_commit`, `code_head`, `selection_strategy_id`, `replay_identity`, `selection_domain`, `group_domain`, `parent_reuse_manifest_sha256`, `parent_current_preflight_sha256`, `candidate_domain_counts`, `group_count`, `singleton_group_count`, `non_singleton_group_count`, `cross_split_group_count`, `excluded_non_owner_count`, `group_counts_by_family`, `group_counts_by_split`, `group_size_histogram`, `owner_counts_by_family_split`, `groups`, `problems`.

Counts are ordered arm -> family -> split; family order is MAP/REST/REWARDS/TREASURE; split order is train/validation/heldout; histogram is ascending group size; groups are ascending group digest. Ordered parents are `[stage0-retained-source-reuse.json, stage0-preflight.json]` by persisted SHA-256.

### `t075-source-selection-manifest-v1`

Required: `schema_id`, `schema_version`, `task_id`, `approved_t075_spec_commit`, `code_head`, `selection_strategy_id`, `parent_reuse_manifest_sha256`, `parent_current_preflight_sha256`, `parent_ownership_audit_sha256`, `selected_states_path`, `selected_states_sha256`, `selected_state_schema_id=t065-source-state-v1`, `selected_state_file_format=t065-source-state-jsonl-v1`, frozen family/split order, quotas, `post_owner_available_counts`, `selected_counts`, `selected_replay_identity_digests`, `replay_verification`, `problems`.

Ordered parents are `[stage0-retained-source-reuse.json, stage0-preflight.json, stage1-replay-group-ownership-audit.json]`. `stage1-selected-states.json` is UTF-8 JSONL, exactly one complete `t065-source-state-v1` object per line, indices `0..319`, no wrapper, final newline. Replay requires 320 attempted/restored and zero mismatch/replacement/selected duplicate/cross-split overlap.

## Stage 3 is a mandatory Stage-2 subphase

T075 explicitly chooses review option (a): Stage 3 is not a separate command. The Stage-2 `target` command includes a mandatory post-generation validation subphase. Execution stage name remains `stage2-target`; it is incomplete until Stage-3 validation passes.

After target generation and before a completed Stage-2 retention manifest, the command must:

1. reopen the persisted target table with strict `read_target_table`;
2. apply complete-table validation equivalent to current `T065TargetTable.validate_complete()`;
3. verify actual target-table path/hash/size and selected-state path/hash/size/record count;
4. verify 320 selected states, indices `0..319`, and exact per-family 48/16/16 split counts;
5. verify every eligible legal action has exactly one target, correct legal order, correct split-specific continuation seeds, finite `q_floor`, and no state/action replacement or omission;
6. verify exact `non-combat-model-input-v1` v1, state/action dimensions 4737/92, finite features, frozen order/missing/OOV semantics;
7. verify selection/source lineage, fresh T075 preflight identity, simulator identity, and Stage-1 retention parents;
8. run the existing public-input firewall/strict source-model validation so behavior action, expert score/prior, target/outcome, hidden future, native checkpoint/payload, hidden RNG/draw order, or other forbidden public-context fields cannot enter deployable input;
9. atomically write `stage2-target-validation.json` and only then mark `stage2-target` completed.

`stage2-target-validation.json` schema is `t075-stage3-validation-report-v1` and requires:

```text
schema_id = t075-stage3-validation-report-v1
schema_version = 1
task_id = T075
approved_t075_spec_commit
code_head
execution_stage = stage2-target
logical_stage = stage3-model-input-lineage-firewall
parent_target_table_sha256
parent_selected_states_sha256
parent_selection_manifest_sha256
parent_current_preflight_sha256
selected_state_count = 320
target_row_count
eligible_action_count
family_split_state_counts
continuation_replication_counts_by_split
checks
violation_counts
passed
problems
```

`checks`, in order: `strict_target_reader`, `target_completeness`, `selected_state_lineage`, `simulator_and_preflight_lineage`, `model_input_schema`, `state_action_dimensions`, `finite_numeric_values`, `legal_action_order`, `continuation_seed_contract`, `public_input_firewall`. Each records `status=passed|failed` plus deterministic counts.

`violation_counts` requires: `missing_target_rows`, `duplicate_target_rows`, `nonfinite_targets`, `model_input_mismatches`, `lineage_mismatches`, `legal_action_mismatches`, `continuation_seed_mismatches`, `firewall_violations`.

Any failed check is Case D with `terminal_stage=stage2-target`, `reason_code=stage3-validation-failed`. Failed validation may retain target/validation files as failed-stage evidence but may not emit a completed `stage2-target-table.retention.json`. Stage 4 cannot start.

A completed Stage-2 retention manifest must contain both target table and validation report as outputs and record `stage3_validation_status=passed` in `stage_evidence["stage2-target"]`.

## Terminal decision schema

`t075-terminal-decision-report-v1` is canonical UTF-8 JSON, sorted keys, compact separators, `ensure_ascii=False`, `allow_nan=False`, one trailing newline. Required:

```text
schema_id = t075-terminal-decision-report-v1
schema_version = 1
task_id = T075
approved_t075_spec_commit
planner_baseline
code_head
terminal_case = A | B | C | D
terminal_stage = stage0-preflight | stage0-reuse | stage1-selection-replay | stage2-target | stage4-train | stage5-gate | stage6-eval
reason_code
summary
reached_stages
skipped_stages
parent_artifact_identities
stage3_validation_status = passed | failed | not_reached
stage5_gate_status = passed | failed | not_reached
stage6_status = completed | skipped | not_reached
recommendation
problems
```

Stage-3 failure is terminal stage `stage2-target`. Stage 0/1/2/4 fidelity/completeness failures are Case D; valid Stage-5 gate failure is Case C; valid Stage-5 pass authorizes Stage 6; Stage 6 writes Case A/B or Stage-6 Case D. First valid terminal report wins; downstream scientific stages are skipped and may not rewrite semantic content. Every stage uses the same explicit `--decision-report "$ROOT/terminal-decision-report.json"`. Finalization validates/retains rather than reinterprets.

## Final retention schema

`t075-retention-manifest-v1` requires `schema_id`, `schema_version`, `task_id`, `approved_t075_spec_commit`, `planner_baseline`, `terminal_case`, `retention_owner=T075`, `retention_reason`, `reused_artifacts`, `produced_artifacts`, `stage_commands`, `stage_evidence`, `downstream_consumers`, `deletion_condition`, `problems`.

Execution-stage order is exactly:

`stage0-preflight`, `stage0-reuse`, `stage1-selection-replay`, `stage2-target`, `stage4-train`, `stage5-gate`, `stage6-eval`, `terminal-finalize`.

Stage 3 has no separate execution entry; its status/output is part of `stage2-target`. Each command entry records exact command, executed/skipped, skip reason, code head, start/end, exit/terminal status, wall-clock, shard/worker/ranges, parent identities, output identities. Each evidence entry records executed flag, terminal status, code head, shard/worker/ranges, per-shard return status, wall-clock, parent/output identities, counts, and problems.

## Frozen sharding

Stage-1 replay and Stage-2 target generation use exactly 16 contiguous 20-state shards:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested/required actual worker count is 16, at most 16 concurrent simulator workers. Failure to establish this plan is Case D before the substantial run.

## Frozen commands

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

Local gates:

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
  --retention-manifest "$ROOT/stage0-preflight.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Reuse validation:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning validate-reuse \
  --source "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --source "$T065/source-expert-650001-650256-deeaa46.json" \
  --accepted-preflight-content-sha256 a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334 \
  --source-preflight-alias "$T065/preflight-c57b2ee-20260827.json" \
  --source-preflight-alias "$T065/preflight-968797e-20260827.json" \
  --source-preflight-retention-alias "$T065/preflight-c57b2ee-20260827.retention.json" \
  --source-preflight-retention-alias "$T065/preflight-968797e-20260827.retention.json" \
  --accepted-case-d "$T065/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json" \
  --accepted-case-d-retention "$T065/source-selection-650001-650256-a69972f.retention.json" \
  --output "$ROOT/stage0-retained-source-reuse.json" \
  --retention-manifest "$ROOT/stage0-retained-source-reuse.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Stage 1:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning select \
  --input "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --input "$T065/source-expert-650001-650256-deeaa46.json" \
  --selection-strategy leakage-safe-global-owner-v1 \
  --reuse-manifest "$ROOT/stage0-retained-source-reuse.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --output "$ROOT/stage1-selected-states.json" \
  --ownership-audit "$ROOT/stage1-replay-group-ownership-audit.json" \
  --manifest "$ROOT/stage1-selection-manifest.json" \
  --replay-verify --replay-shard-count 16 --replay-worker-count 16 \
  --retention-manifest "$ROOT/stage1-selection.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

No `collect` command is allowed in T075.

Stage 2 + mandatory logical Stage 3:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning target \
  --states "$ROOT/stage1-selected-states.json" \
  --selection-manifest "$ROOT/stage1-selection-manifest.json" \
  --output "$ROOT/stage2-target-table.json" \
  --validation-report "$ROOT/stage2-target-validation.json" \
  --shard-count 16 --worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage1-selection.retention.json" \
  --retention-manifest "$ROOT/stage2-target-table.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

There is no separate Stage-3 command. This command succeeds only after `t075-stage3-validation-report-v1` passes.

Stage 4:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --target-validation "$ROOT/stage2-target-validation.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage2-target-table.retention.json" \
  --retention-manifest "$ROOT/stage4-training.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Before any optimizer step Stage 4 must validate `passed=true`, validation parent hashes, and that completed Stage-2 retention contains both target and validation artifacts. Model seeds remain exactly 653001/653002, two processes maximum, `torch_threads=1` each.

Stage 5:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --retention-manifest "$ROOT/stage5.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Valid Stage-5 failure is Case C; pass authorizes Stage 6.

Stage 6:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --stage5-report "$ROOT/stage5-heldout-report.json" \
  --output "$ROOT/stage6-complete-run-report.json" \
  --run-stage6 --stage6-shard-count 16 --stage6-worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage5.retention.json" \
  --retention-manifest "$ROOT/stage6.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Stage 6 remains three matched arms x 16 shards x 16 fresh seeds, seeds `651001..651256`, 768 terminal runs for a valid complete stage.

Finalization:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json"
```

Finalization validates/retains an existing terminal report and may not infer another case.

## Retention and failure rules

T075 owns retention of both raw T065 sources from implementation authorization until its terminal result merges. Deletion requires a merged terminal T075 report/compact retention manifest, no open/approved task requiring the inputs, no Maintainer reproduction hold, and retained compact downstream evidence. T075 never deletes sources during execution.

Case D includes source-resolver mismatch/ambiguity, invalid preflight alias/content/provenance, path normalization failure, wrong/dirty checkout, approved-spec ancestry failure, fresh-preflight failure, owner-key tie, quota shortfall, selected replay failure, target incompleteness, logical Stage-3 model-input/lineage/firewall failure, simulator/provenance mismatch, or forbidden truncation. Source recollection or tuning the ownership rule to recover is forbidden.

The implementation report must include exact approved spec and code head per stage, source resolver identities/evidence, raw-source metadata checks, historical preflight aliases/full hashes, fresh preflight identity, ownership/group statistics, post-owner/selected counts, Stage-1 replay evidence, Stage-2 target and logical Stage-3 validation counts/status, all reached/skipped stage commands/evidence, terminal-decision identity/parents, artifacts/hashes/sizes/parents, full/focused verification, costs, exactly one terminal Case A/B/C/D, and exactly one next recommendation.
