# T075 Normative Execution, Reuse, And Artifact Contract

This file is normative together with [`T075-leakage-safe-non-combat-cohort-repair.md`](T075-leakage-safe-non-combat-cohort-repair.md). It freezes execution checkout/runtime, retained inputs, source-manifest resolution, path normalization, commands, sharding, Stage-3 validation placement, artifact schemas, ordering, retention, terminal-decision materialization, and failure rules. Material changes after exact-head approval require Maintainer re-approval.

## Code Checkout And Artifact Roots

Scientific execution uses exactly this isolated worktree:

```text
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
BRANCH = task/T075-leakage-safe-non-combat-cohort-repair
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
```

Stable artifacts remain outside the disposable worktree:

```text
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

Every scientific command runs from `CODE` with `PYTHONPATH=${NATIVE}:${CODE}/src`; importing project code from `/mnt/d/DeadlycatCoding/STSRL/src` is forbidden.

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

`terminal-decision-report.json` is the only authoritative T075 terminal-decision path. No command may emit or retain `*.t065-terminal-decision-report.json` during T075.

## Exact Retained T065 Inputs

Approved T065 specification:

`a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`

Required raw source inputs, never recollected by T075:

| Arm | Repository-relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Accepted final lineage evidence:

```text
accepted_preflight_content_sha256 = a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334
case_d_decision_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json
case_d_decision_bytes = 198842
case_d_decision_sha256 = 0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc
case_d_retention_path = artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.retention.json
case_d_retention_bytes = 36186
case_d_retention_sha256 = fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf
```

The older `deeaa46-retry2` decision/retention files are not accepted final T065 Case-D evidence.

### Path normalization

For retained-manifest path comparisons, normalize to repository-relative POSIX paths:

1. replace backslashes with `/`;
2. strip one exact prefix if present: `D:/DeadlycatCoding/STSRL/` or `/mnt/d/DeadlycatCoding/STSRL/`;
3. strip one leading `./`;
4. collapse `.` and reject any `..` component;
5. require prefix `artifacts/`;
6. compare the case-sensitive normalized string exactly.

No basename-only comparison is valid.

### Accepted historical preflight aliases

The two retained source manifests used different historical preflight aliases. T075 accepts exactly:

| Source arm | Raw preflight alias | Retention alias |
|---|---|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.json` | `artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.retention.json` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.json` | `artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.retention.json` |

For either arm, the raw alias must exist at that exact normalized path, hash to `a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334`, parse with the accepted T065 preflight schema/version, record approved T065 spec `a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`, and match the pinned simulator/controller/action-space identity. The corresponding retention alias must parse successfully and reference that raw alias. The validator computes and records the full persisted retention-alias SHA-256; it does not guess a full hash from review-comment prefixes.

### Mechanically frozen source-retention resolver

The resolver is exactly two-level and does not recursively scan lineage references.

For each required raw source independently:

1. Enumerate only files matching `T065/*.retention.json`, in normalized path order.
2. Strict-read each candidate as `t065-retention-manifest-v1`, schema version `1`, `task_id="T065"`, approved spec `a13c92a66b4ad25a7b0bdc8097cc0cfdc26dffa`, with valid `artifacts`, `stage_evidence`, `preceding_stage_manifests`, `regeneration_commands`, `simulator_identity`, and `frozen_config` fields.
3. A retention manifest is a candidate for this source only when `artifacts[]` contains exactly one entry whose `role == "current_output"` and whose normalized `path`, `size_bytes`, and `sha256` equal the frozen raw-source identity above. Mentions under `preceding_stage_manifests`, including the accepted final Case-D manifest's references to both source manifests, are never matching discriminators.
4. Exactly one candidate manifest must remain. Zero or more than one is Case D at `source-input-reuse`.
5. For that candidate manifest, require `stage_evidence["stage1-source-collection"]` with:
   - `stage == "stage1-source-collection"`;
   - `status == "completed"`;
   - `terminal is false`;
   - `artifact_roles` containing `current_output`;
   - `preceding_stage_manifests["stage0_preflight"]` equal to the arm-specific accepted preflight-retention alias descriptor after path/hash/size validation;
   - non-empty `command` equal to the sole entry in top-level `regeneration_commands`.
6. The retention manifest's top-level `frozen_config` must equal the frozen `T065ExperimentConfig().to_dict()` and top-level `simulator_identity` must equal the pinned current identity. These fields prove retained workflow configuration; command text is retained as provenance and is not parsed to infer scientific counts.
7. All source-arm/completeness predicates are proved from the referenced raw source JSON metadata, not guessed from retention-stage text. The exact authoritative top-level raw-source fields are:
   - `schema_id == "t065-learned-non-combat-policy-v1"`, `schema_version == 1`;
   - `approved_spec_commit == a13c92a66b4ad25a7b0bdc8097cc0cfdc26dffa`;
   - `frozen_config == T065ExperimentConfig().to_dict()`;
   - `arm` equals the expected arm;
   - `driver_seed == 654001`;
   - `requested_seed_count == 256`;
   - `terminal_run_count == 256`;
   - `truncated_run_count == 0`;
   - `failed_run_count == 0`;
   - `selected_candidate_count == len(records)`;
   - `problems == []`;
   - `worker_count == 16`;
   - `shard_count == 16`;
   - `action_space == ActionSpaceConfig.initial_no_potions().to_dict()`;
   - `battle_controller_provenance == frozen_battle_provenance()` with name `oracle_search_v1_highest_mean_s20`;
   - `simulator_identity == lightspeed_source_identity_dict()`;
   - `run_summaries` contains exactly 256 terminal, problem-free summaries for simulator seeds `650001..650256`, each with matching `source_arm` and `source_run_id == f"{arm}:{seed}"`.
8. `shard_specs` must contain exactly 16 ordered entries. For shard index `i=0..15`, require `shard_index=i`, `seed_start=650001+16*i`, `seed_end=650016+16*i`, `seed_count=16`, `worker_count=16`, `requested_seed_count=16`, `terminal_run_count=16`, `truncated_run_count=0`, `failed_run_count=0`, and empty `problems`.
9. The candidate source manifest must point through its `stage0_preflight` lineage to the arm-specific c57/968 alias pair above. Preserve the source-manifest path/hash, raw-source path/hash/size, preflight raw path/hash, preflight retention path/full computed hash, and exact original regeneration command in T075 reuse evidence.

Any mismatch is Case D at `source-input-reuse`. T075 never recollects either source.

## Candidate Domain And Global Ownership

Ownership admits only strict-reader-valid `t065-source-state-v1` rows whose source run has `terminal == true`, family is exactly one of `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`, simulator seed maps to the frozen T065 split, and existing T065 public/model/action/replay/provenance checks pass. Nonterminal/truncated rows remain audited evidence but cannot become owners or selected states. Malformed/provenance-invalid rows are Case D.

Replay-equivalence key remains exactly:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON uses UTF-8, sorted keys, separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, with no newline in digest bytes.

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_payload = {
  "family": family,
  "public_state_identity": public_state_identity,
  "ordered_legal_action_identities": ordered JSON-safe identity mappings
}
group_digest = sha256(T075_GROUP_DOMAIN + canonical_json(group_payload)).hexdigest()
```

Groups serialize ascending by `group_digest`. Member ordering remains T065:

```text
selection_digest = sha256(
  b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

If distinct rows tie on the full pair, Case D at `cohort-ownership`; do not add another tie-break field. Otherwise the first member is the sole owner and keeps its simulator-seed split. All non-owners are excluded before quota selection. Selection strategy id is `leakage-safe-global-owner-v1`.

## Artifact Schemas

Every T075 schema below has `schema_version = 1`. Missing required fields, wrong version/order, non-finite values, parent mismatch, or required file/hash mismatch fails closed.

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
accepted_t065_preflight_content_sha256
accepted_t065_case_d
sources
validation
original_regeneration_commands
problems
```

`sources` is ordered stochastic then expert. Each entry records raw path/size/hash, expected arm, strict raw-metadata validation result, matched source-retention path/hash, `current_output` discriminator identity, exact `stage1-source-collection` evidence, top-level frozen config/simulator identity, referenced preflight raw/retention aliases and full hashes, and compatibility status.

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
parent_current_preflight_sha256
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

`candidate_domain_counts` is ordered arm -> family -> split and records raw, terminal, nonterminal-excluded, unsupported-family-excluded, and valid-terminal counts. `group_counts_by_family` uses frozen family order. `group_counts_by_split` uses train/validation/heldout order. `group_size_histogram` is ascending integer group size. `owner_counts_by_family_split` contains the 12 family-major/split-minor owner counts before quota selection. `groups` is ascending by group digest and records family, size, represented splits, cross-split flag, ordered members, owner or null, and exclusion count.

Ordered parents are exactly `[stage0-retained-source-reuse.json, stage0-preflight.json]` by persisted SHA-256.

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
parent_current_preflight_sha256
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

Ordered parents are `[stage0-retained-source-reuse.json, stage0-preflight.json, stage1-replay-group-ownership-audit.json]`. `stage1-selected-states.json` is UTF-8 JSONL with exactly one complete `t065-source-state-v1` object per line, selected indices `0..319` in order, no wrapper, and one final newline. Replay verification requires 320 attempted/restored, zero mismatch/replacement, zero selected replay duplicate, and zero selected cross-split replay overlap.

### Stage 3 placement: mandatory validation inside Stage 2

T075 chooses Maintainer option (a): there is no independent Stage-3 command or worker stage. Stage 3 is a mandatory post-generation validation subphase inside the Stage-2 `target` command. The execution stage remains `stage2-target`, but it is not complete until this subphase passes.

The Stage-2 command must, after writing the target table and before writing a completed Stage-2 retention manifest:

1. reopen `stage2-target-table.json` through the strict current `read_target_table` reader;
2. call the existing complete-table validation semantics equivalent to `T065TargetTable.validate_complete()`;
3. verify the persisted target-table SHA-256/size and parent selected-state path/hash/size/record-count;
4. verify exactly 320 selected states with family/split counts 48/16/16 and indices `0..319`;
5. verify every eligible legal action has exactly the frozen target representation, no missing/duplicate action target, correct legal-action order, correct continuation-seed contract for the state's split, finite `q_floor`, and no dropped/replaced state/action;
6. verify `model_input_schema` equals exact `non-combat-model-input-v1` v1 and every state/action vector has dimensions 4737/92 with finite values and frozen ordering/missing/OOV semantics;
7. verify selected-state/selection-digest/source-artifact lineage, target-table simulator identity, fresh T075 preflight identity, and Stage-1 selection-retention identity all match their ordered parents;
8. run the public-input firewall through the existing strict source/model-input validation: no behavior action, expert score/prior, target/outcome, hidden future, native checkpoint/payload, hidden RNG/draw order, or other forbidden public-context field may enter model input;
9. write `stage2-target-validation.json` and only then mark `stage2-target` completed.

`stage2-target-validation.json` schema is `t075-stage3-validation-report-v1` with required fields:

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

`checks` contains, in this exact order: `strict_target_reader`, `target_completeness`, `selected_state_lineage`, `simulator_and_preflight_lineage`, `model_input_schema`, `state_action_dimensions`, `finite_numeric_values`, `legal_action_order`, `continuation_seed_contract`, `public_input_firewall`. Each has `status=passed|failed` and deterministic counts. `violation_counts` contains `missing_target_rows`, `duplicate_target_rows`, `nonfinite_targets`, `model_input_mismatches`, `lineage_mismatches`, `legal_action_mismatches`, `continuation_seed_mismatches`, and `firewall_violations`.

Any failed check is Case D with `terminal_stage=stage2-target` and `reason_code=stage3-validation-failed`. A failed validation may retain the target table and validation report as failed-stage evidence but must not emit a completed `stage2-target-table.retention.json`. Stage 4 must not start.

A completed `stage2-target-table.retention.json` must include both `stage2-target-table.json` and `stage2-target-validation.json` as Stage-2 outputs and must record `stage3_validation_status=passed` in `stage_evidence["stage2-target"]`.

### `t075-terminal-decision-report-v1`

`terminal-decision-report.json` uses canonical UTF-8 JSON with sorted keys, compact separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, and one trailing newline. Required fields:

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

Stage-3 validation failure is reported under terminal stage `stage2-target`. Any Stage 0/1/2/4 fidelity/completeness failure is Case D; valid Stage-5 gate failure is Case C; valid Stage-5 pass authorizes Stage 6; Stage 6 writes Case A/B or Stage-6 Case D. After the first valid terminal report exists, downstream scientific stages are skipped and no later command may change its semantic content. Every scientific command receives the same `--decision-report "$ROOT/terminal-decision-report.json"`; `finalize` validates and retains the existing report rather than inferring another case.

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

`stage_commands` and `stage_evidence` use execution-stage order:

`stage0-preflight`, `stage0-reuse`, `stage1-selection-replay`, `stage2-target`, `stage4-train`, `stage5-gate`, `stage6-eval`, `terminal-finalize`.

Stage 3 is not a separate execution entry; its passed/failed evidence is part of `stage2-target`, whose outputs include the validation report. Each stage-command entry records exact command, executed/skipped status, skip reason, code head, start/end, exit/terminal status, wall-clock, shard/worker/range evidence, parent identities, and output identities. Each stage-evidence entry records executed flag, terminal status, code head, shard/worker/ranges, per-shard return status, wall-clock, parent/output identities, counts, and problems.

## Stage 1 Replay Sharding

After owner/quota selection assigns indices `0..319`, replay verification is exactly 16 contiguous shards of 20 indices:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested and required actual worker count is 16, with at most 16 concurrent simulator workers. Failure to establish that plan is Case D before replay.

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
  --retention-manifest "$ROOT/stage0-preflight.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Retained-source reuse validation:

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

Stage 1 selection/replay:

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

No `collect` invocation is permitted in T075.

Stage 2 target generation plus mandatory Stage-3 validation:

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

Stage 2 uses the same 16 x 20 selected-index ranges and frozen continuation actions/seeds. This command is successful only after `t075-stage3-validation-report-v1` passes and is persisted. There is no separate Stage-3 command.

Stage 4 training:

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

Stage 4 must verify the validation artifact is `passed=true`, its target-table/selected-state/preflight parent hashes match the actual inputs, and the completed Stage-2 retention manifest contains both target and validation outputs. Otherwise Case D before any optimizer step. Exactly model seeds 653001/653002 are trained; two processes may run concurrently, each with `torch_threads=1`.

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

Valid Stage-5 failure is Case C and writes the terminal report; valid Stage-5 pass authorizes Stage 6.

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
  --retention-manifest "$ROOT/stage6.retention.json" \
  --decision-report "$ROOT/terminal-decision-report.json"
```

Stage 6 remains three matched arms x 16 shards x 16 seeds, fresh seeds `651001..651256`, at most 16 concurrent simulator workers, 768 terminal runs for a valid complete stage.

Finalization:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json"
```

`finalize` requires an already valid `t075-terminal-decision-report-v1`; it validates and retains it and must not infer or replace terminal semantics.

## Retention And Failure Rules

T075 owns retention of both raw T065 sources from implementation authorization until its terminal result merges. They are retained because they are the unique approved source evidence for deterministic repaired cohort construction. They may be deleted only after a merged terminal T075 report/compact retention manifest, no open/approved task still requires them, Maintainer records no pending reproduction need, and accepted compact downstream evidence is retained. T075 never deletes them during execution.

Case D includes retained-input resolver mismatch/ambiguity, invalid preflight alias/content/provenance, path-normalization failure, wrong/dirty checkout, approved-spec ancestry failure, fresh-preflight failure, exact owner-key tie, insufficient owner bucket, selected replay failure, target incompleteness, Stage-3 validation/firewall/lineage/model-input failure, simulator/provenance mismatch, or forbidden truncation. T075 may not recollect sources or tune ownership to recover.

The implementation report must include exact approved spec, code head per stage, normalized input identities, matched source-manifest discriminator/evidence, raw-source metadata validation, preflight aliases/full hashes, fresh-preflight parent identity, ownership counts by family/split/group size, post-owner/selected counts, Stage-1 replay evidence, Stage-2 target and Stage-3 validation counts/status, reached/skipped stage commands/evidence, terminal-decision identity/parents, artifact hashes/sizes/parents, full/focused verification, costs, exactly one terminal Case A/B/C/D, and exactly one next recommendation.
