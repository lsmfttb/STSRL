# T075 Normative Execution, Reuse, And Artifact Contract

This file is a normative part of T075 together with
[`T075-leakage-safe-non-combat-cohort-repair.md`](T075-leakage-safe-non-combat-cohort-repair.md).
It freezes the code checkout, runtime, retained inputs, path normalization,
command templates, sharding, artifact schemas, ordering, retention, and failure
rules. If the primary task document is less specific on these details, this file
controls. Any material change after exact-head approval requires Maintainer
re-approval. This file does not authorize implementation by itself.

## 1. Frozen Code Checkout, Runtime, And Stable Artifact Roots

Scientific execution must use the isolated T075 worktree:

```text
code_checkout_windows = D:\DeadlycatCoding\STSRL\.claude\worktrees\t075-leakage-safe-non-combat-cohort-repair
code_checkout_wsl = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
branch = task/T075-leakage-safe-non-combat-cohort-repair
python = /home/lsmft/stsrl-spikes/py313-torch/bin/python
native_pythonpath = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
project_pythonpath = ${code_checkout_wsl}/src
```

The stable artifact roots are outside the disposable task worktree:

```text
stable_repository_root_windows = D:\DeadlycatCoding\STSRL
stable_repository_root_wsl = /mnt/d/DeadlycatCoding/STSRL
t075_artifact_root = /mnt/d/DeadlycatCoding/STSRL/artifacts/t075-leakage-safe-non-combat-cohort-repair
t065_artifact_root = /mnt/d/DeadlycatCoding/STSRL/artifacts/t065-learned-non-combat-policy-v1
```

Every scientific command must run with `cwd=code_checkout_wsl` and
`PYTHONPATH=${native_pythonpath}:${code_checkout_wsl}/src`. No command may import
project code from `/mnt/d/DeadlycatCoding/STSRL/src`.

Before the first scientific stage and again before each later simulator/training
stage, record and require:

```bash
CODE=/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
cd "$CODE"
test "$(git branch --show-current)" = "task/T075-leakage-safe-non-combat-cohort-repair"
test -z "$(git status --porcelain)"
APPROVED_SPEC={APPROVED_T075_SPEC_COMMIT}
git merge-base --is-ancestor "$APPROVED_SPEC" HEAD
CODE_HEAD=$(git rev-parse HEAD)
```

`{APPROVED_T075_SPEC_COMMIT}` is replaced only by the exact commit named in the
Maintainer `SPEC APPROVED` comment. The implementation head may advance on this
same branch after approval, but every executed stage must record its exact
`CODE_HEAD`. Branch switching is forbidden. A dirty worktree, wrong branch, or
approved-spec-not-ancestor check is Case D before the affected stage.

Shell variables for all WSL scientific commands are:

```bash
CODE=/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
STABLE=/mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT=$STABLE/t075-leakage-safe-non-combat-cohort-repair
T065=$STABLE/t065-learned-non-combat-policy-v1
PY=/home/lsmft/stsrl-spikes/py313-torch/bin/python
export PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch:$CODE/src
cd "$CODE"
```

## 2. Frozen T075 Output Paths

The stable outputs are exactly:

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

All paths above are below `t075_artifact_root`. Temporary shard files may live in
stage-local temporary directories below that root and must be deleted after a
successful merge or listed explicitly as retained failed-stage evidence.

## 3. Exact Retained T065 Inputs

T075 reuses and must not regenerate the two raw Stage 1 sources:

| Arm | Repository-relative path | Exact bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Additional accepted T065 lineage evidence is exactly:

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

The older `deeaa46-retry2` decision/retention files are not accepted final T065
Case-D identities and must not satisfy the T075 lineage gate.

### Path normalization rule

Artifact identities are compared using canonical repository-relative POSIX paths.
Normalize any path from a retained manifest as follows before comparison:

1. replace `\\` with `/`;
2. map Windows prefix `D:/DeadlycatCoding/STSRL/` and WSL prefix
   `/mnt/d/DeadlycatCoding/STSRL/` to the empty prefix;
3. remove one leading `./` if present;
4. collapse `.` components but reject any `..` component;
5. require the result to begin with `artifacts/`;
6. compare the resulting case-sensitive POSIX string exactly to the
   repository-relative paths frozen above.

A path outside the stable repository root, a path that cannot be normalized by
these rules, or a normalized path mismatch is Case D. No basename-only matching
is allowed.

### Source manifest resolution

For each raw source, inspect only `*.retention.json` files directly below the
T065 artifact root. A retention manifest matches only if it records, after path
normalization, the exact raw path, byte size, SHA-256, source arm, approved T065
spec `a13c92a66b4ad25a7b0bdc8097cc0cfdc26dffa` is **not** accepted; the approved
T065 specification must be exactly
`a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`, source seed range `650001..650256`,
driver seed `654001`, pinned simulator identity, battle controller
`oracle_search_v1_highest_mean_s20`, exact `initial_no_potions` action-space
identity, 16 source shards, 16 effective workers, 256 requested terminal runs,
and zero truncations.

Exactly one manifest must match each raw source. Zero or multiple matches are
Case D at `source-input-reuse`. Preserve the original regeneration command text
from each matched manifest in the T075 reuse manifest for provenance only; T075
must not execute those commands.

## 4. Candidate Domain And Global Ownership

The selectable candidate domain is:

1. strict-reader-valid `t065-source-state-v1` rows from the two raw sources;
2. source run `terminal == true`;
3. family exactly one of `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`;
4. simulator seed in its unchanged T065 train/validation/heldout seed group;
5. all existing T065 public/model/action/replay/provenance checks pass.

Nonterminal/truncated rows remain source evidence but are not selectable and may
never become owners. Malformed or provenance-invalid rows fail closed rather
than being silently excluded.

The T065 replay-equivalence key is unchanged:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical JSON used for T075 content digests is UTF-8, sorted keys, compact
separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`, and no trailing
newline in the bytes used for a digest.

### Replay-group digest

The payload is exactly:

```json
{
  "family": "<family>",
  "public_state_identity": "<identity>",
  "ordered_legal_action_identities": [<existing JSON-safe identity mappings in order>]
}
```

Define:

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_payload_bytes = canonical_json(group_payload)
group_digest = sha256(T075_GROUP_DOMAIN + group_payload_bytes).hexdigest()
```

Groups are serialized ascending by `group_digest`.

### Member order and ties

Reuse the T065 key exactly:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Members are ordered lexicographically by that pair. If two distinct source rows
in one replay group have an identical pair, T075 is Case D at
`cohort-ownership`. Report every tied row's source arm, seed, run id, source step,
split, public-state identity, and group digest. Do not add input order, worker
completion order, private state, occurrence index, or another tie-break field.

Otherwise the first member is the sole owner. All non-owners are excluded before
quota selection. The owner retains the split implied by its simulator seed.

Selection strategy id is exactly:

`leakage-safe-global-owner-v1`

## 5. Required T075 Artifact Schemas

All schemas below use `schema_version = 1`. Required fields may not be omitted or
silently defaulted. Unknown additive fields are allowed only when they do not
change interpretation. Readers fail closed on wrong version, missing required
field, invalid ordering, parent mismatch, non-finite numeric value, or required
file/hash mismatch.

### 5.1 `t075-retained-source-reuse-manifest-v1`

Required top-level fields in this semantic order:

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

`sources` order is stochastic then expert. Each entry requires normalized path,
absolute stable path, persisted bytes, SHA-256, source schema/version, source
arm, seed range, driver seed, controller/action-space provenance,
terminal/truncation counts, shard/worker evidence, resolved T065 retention
manifest normalized path/absolute path/hash, and compatibility result.

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

Aggregate semantics and ordering are exact:

- `candidate_domain_counts`: source arm order stochastic/expert, then family order
  MAP/REST/REWARDS/TREASURE, then split order train/validation/heldout; each row
  records raw, terminal, nonterminal-excluded, unsupported-family-excluded, and
  valid-terminal counts;
- `group_counts_by_family`: four rows in frozen family order; each records total,
  singleton, non-singleton, cross-split, and excluded-non-owner counts;
- `group_counts_by_split`: three rows train/validation/heldout; `present_group_count`
  counts each replay group once for each split containing at least one member,
  `owner_group_count` counts groups whose owner is in that split, and
  `cross_split_present_group_count` counts cross-split groups containing that
  split;
- `group_size_histogram`: rows sorted by integer `group_size` ascending, each with
  `group_count`; the sum of `group_count` equals `group_count` above;
- `owner_counts_by_family_split`: 12 rows, family-major then split-minor, with the
  number of surviving owners before quota selection.

`groups` is ascending by group digest. Each group records digest, family, size,
splits represented in frozen split order, cross-split bool, ordered members,
owner or null, and excluded count. Each member records arm, seed, run id, source
step, split, public-state identity, selection digest, and canonical-candidate
SHA-256. An exact member-order tie requires `owner=null`, complete tie evidence,
and Case D.

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
family_order
split_order
quotas
post_owner_available_counts
selected_counts
selected_replay_identity_digests
replay_verification
problems
```

`stage1-selected-states.json` is the current T065 JSONL row format: UTF-8, exactly
one complete `t065-source-state-v1` JSON object per line, no wrapper array/object,
rows ordered by selected-state index `0..319`, and exactly one newline after each
row including the final row. The strict current T065 source-state reader must
round-trip all 320 rows.

`post_owner_available_counts` and `selected_counts` use family-major,
split-minor order. Quotas are 48/16/16. `replay_verification` must include the
Stage 1 shard/worker evidence below and 320 attempted/restored, zero mismatch,
zero replacement, zero selected replay duplicate, and zero selected cross-split
overlap.

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

`produced_artifacts` is stage ordered. Each item records normalized path, absolute
stable path, persisted bytes, SHA-256, schema id/version, producer stage,
code-head identity, and ordered parent artifact identities.

`stage_commands` contains exactly one entry per frozen logical stage in order:
`stage0-preflight`, `stage0-reuse`, `stage1-selection-replay`, `stage2-target`,
`stage4-train`, `stage5-gate`, `stage6-eval`, `terminal-finalize`. Each entry has:

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

Skipped stages have `exit_code=null`, timestamps/wall-clock null, explicit
`skip_reason`, and empty output identities.

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

For non-sharded stages, shard/worker/range fields are null/empty as appropriate.
For skipped stages, `executed=false`, `terminal_status=skipped`, all runtime
counts empty, and `problems` empty unless the prior terminal case records the
skip reason in `stage_commands`.

## 6. Stage 1 Replay Verification Topology

After deterministic ownership and quota selection assigns selected indices
`0..319`, replay verification is exactly 16 shards of 20 contiguous indices:

```text
shard 00: 000..019
shard 01: 020..039
shard 02: 040..059
shard 03: 060..079
shard 04: 080..099
shard 05: 100..119
shard 06: 120..139
shard 07: 140..159
shard 08: 160..179
shard 09: 180..199
shard 10: 200..219
shard 11: 220..239
shard 12: 240..259
shard 13: 260..279
shard 14: 280..299
shard 15: 300..319
```

Requested and target effective worker count is exactly 16, with no more than 16
concurrent simulator workers. If the runtime cannot establish the frozen
16-worker execution plan, stop before replay and record Case D rather than
silently running a substantial single-worker stage.

The Stage 1 manifest/evidence must record shard ranges, requested/actual worker
count, per-shard return status, attempted/restored/mismatch counts, total
wall-clock, code head, and output identities.

## 7. Frozen Command Contract

The implementation may add only the neutral arguments/subcommands named below to
`sts_combat_rl.commands.non_combat_learning`. It must not add a T075 route to the
legacy flat CLI.

### 7.1 Clean-head gate

Run before every scientific stage:

```bash
CODE=/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-leakage-safe-non-combat-cohort-repair
cd "$CODE"
test "$(git branch --show-current)" = "task/T075-leakage-safe-non-combat-cohort-repair"
test -z "$(git status --porcelain)"
APPROVED_SPEC={APPROVED_T075_SPEC_COMMIT}
git merge-base --is-ancestor "$APPROVED_SPEC" HEAD
```

### 7.2 Local/focused verification

From `CODE`:

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

### 7.3 Stage 0 runtime preflight

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --retention-manifest "$ROOT/stage0-preflight.retention.json"
```

### 7.4 Stage 0 retained-input validation

The implementation adds neutral subcommand `validate-reuse` with this exact
shape:

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

This validates path normalization, exact sizes/hashes, manifest resolution,
source schema/provenance, and accepted final Case-D lineage. It never runs
`collect`.

### 7.5 Stage 1 ownership, selection, and replay verification

```bash
$PY -m sts_combat_rl.commands.non_combat_learning select \
  --input "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --input "$T065/source-expert-650001-650256-deeaa46.json" \
  --selection-strategy leakage-safe-global-owner-v1 \
  --reuse-manifest "$ROOT/stage0-retained-source-reuse.json" \
  --output "$ROOT/stage1-selected-states.json" \
  --ownership-audit "$ROOT/stage1-replay-group-ownership-audit.json" \
  --manifest "$ROOT/stage1-selection-manifest.json" \
  --replay-verify \
  --replay-shard-count 16 \
  --replay-worker-count 16 \
  --retention-manifest "$ROOT/stage1-selection.retention.json"
```

No `collect` command is permitted in T075. Ownership/selection is deterministic
CPU work; only the selected-state replay verification opens simulator workers.

### 7.6 Stage 2 targets

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

Selected indices are `0..319`; 16 shards own 20 contiguous indices each, using
the same ranges frozen for Stage 1 replay. Each shard owns all eligible actions
and all required continuation seeds for its states.

### 7.7 Stage 4 training

Only after complete Stage 2/3 validation:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage2-target-table.retention.json" \
  --retention-manifest "$ROOT/stage4-training.retention.json"
```

The command trains exactly model seeds 653001 and 653002. The two model processes
may run concurrently; each uses `torch_threads=1`.

### 7.8 Stage 5 held-out gate

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage4-training.retention.json" \
  --retention-manifest "$ROOT/stage5.retention.json"
```

A valid Stage 5 failure is Case C and Stage 6 is skipped.

### 7.9 Conditional Stage 6

Only if the persisted Stage 5 report passes every frozen gate:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning evaluate \
  --target-table "$ROOT/stage2-target-table.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --stage5-report "$ROOT/stage5-heldout-report.json" \
  --output "$ROOT/stage6-complete-run-report.json" \
  --run-stage6 \
  --stage6-shard-count 16 --stage6-worker-count 16 \
  --preflight "$ROOT/stage0-preflight.json" \
  --preceding-manifest "$ROOT/stage5.retention.json" \
  --retention-manifest "$ROOT/stage6.retention.json"
```

The frozen topology is three matched arms x 16 shards x 16 seeds, at most 16
simulator workers at one time, seeds `651001..651256`, and 768 valid terminal
runs for a valid complete Stage 6.

### 7.10 Terminal finalization

Neutral subcommand `finalize` must produce the terminal decision and final
retention manifest from reached stage artifacts without rerunning science:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --decision-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json"
```

## 8. Retention Ownership And Deletion

From implementation authorization until the terminal T075 result is merged,
T075 is the retention owner for both reused raw source files. Retention reason:
they are the unique approved source evidence from which the repaired cohort is
deterministically reproducible. Immediate downstream consumer: T075 Stage 1.
No later stage may scan unselected source rows for target/model decisions.

The raw source files may be deleted only after all conditions hold:

1. T075 has a merged terminal Case A/B/C/D report and compact final retention
   manifest;
2. no open or approved task names either raw source as a required input;
3. Maintainer records that no pending reproduction/review needs the raw sources;
4. for Case A/B/C, the selected 320-state artifact and all accepted downstream
   evidence needed for the result are retained; for Case D at ownership/selection,
   raw sources remain retained until that repair route is explicitly closed or
   superseded.

T075 itself never deletes the reused raw sources during execution.

## 9. Failure Semantics And Acceptance

Missing/ambiguous retained manifests, incorrect final T065 evidence, dirty/wrong
code checkout, code head not descending from approved spec, path normalization
failure, exact owner-key tie, insufficient owner bucket, selected replay failure,
target incompleteness, schema/hidden-field failure, simulator/provenance mismatch,
or forbidden truncation is Case D. Do not recollect sources or alter the owner
rule to recover within T075.

A valid Stage 5 failure is Case C. A valid Stage 5 pass followed by valid Stage 6
failure is Case B. Case A requires every frozen Stage 5 and Stage 6 gate to pass.

The implementation report must include exact approved spec, exact code head for
each executed stage, normalized/absolute reused input identities, ownership
aggregates, Stage 1 replay sharding and worker evidence, every reached stage
command/evidence record, artifact hashes/sizes/parents, full/focused verification,
wall-clock and simulator/search cost, exactly one terminal case, and exactly one
next recommendation.
