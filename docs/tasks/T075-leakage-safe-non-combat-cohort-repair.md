# T075: Leakage-Safe Non-Combat Cohort Repair

## Recovery Scope

This is the single normative Planner contract for the clean T075 recovery line on
PR #77. It supersedes the unmerged T075 specification and implementation history
on PR #75. PR #75 remains an audit record only; its task-specific orchestration,
validator graph, retention discovery, command-token proof, PID/process proof, and
runtime artifacts are not T075 recovery state.

Frozen upstream identities:

```text
RECOVERY_BASE = bc9a6790f36ff036f90dc7f03ba0ff026a16788d
T065_APPROVED_SPEC = a13c92a66b4d9ad9f6a730293cadc8d66b4a699c
STS_LIGHTSPEED_INTEGRATION = fee272f1ae21c283ad2161f55293cfe6d714134a
```

T075 depends on T033, T040, T061, T064, T065, T071, and T074. T034, T063, and
T066 are outside T075.

The task remains `DRAFT` until the Main Maintainer publishes exact-head
`SPEC APPROVED` with `implementation_authorized=true`.

## Objective And Scientific Delta

T065 ended validly as Case D because replay-equivalent source candidates crossed
the frozen seed split. T075 repairs only that cohort-partition defect and, only if
the repaired cohort is valid, continues the otherwise unchanged T065 experiment.

The only new scientific rule is:

> Assign one deterministic global owner to every replay-equivalence group before
> applying the unchanged per-family/per-split quota selection.

T075 does not reinterpret T065's Case D and does not change its target, model,
optimizer, continuation policy, information regime, Stage-5 gate, Stage-6 gate,
or terminal scientific meaning.

## Normative Inheritance From T065

The following merged contracts at `RECOVERY_BASE` remain normative for unchanged
science:

- `docs/tasks/T065-learned-non-combat-policy-v1.md`;
- `docs/tasks/T065-frozen-execution-statistics-contract.md`;
- `docs/tasks/T065-non-combat-model-input-v1.md`;
- strict T065 serializers/readers in
  `src/sts_combat_rl/sim/non_combat_learning.py`.

T075 reuses these existing schema contracts:

```text
t065-source-state-v1
t065-counterfactual-target-table-v1
t065-non-combat-ranker-checkpoint-v1
t065-heldout-gate-report-v1
t065-complete-run-report-v1
t065-readiness-preflight-v1
```

T075 must use the merged T065 serializer/reader semantics for those payloads. It
must not copy their fields into a second T075 schema or create a parallel proof
format. A change to one of those payload meanings is a `CONTRACT_GAP`.

## Information Regime And Non-Scope

T075 remains simulator-generated and public-deployment-safe:

- no human trajectories, human action labels, or strategy annotations;
- no expert-policy imitation target;
- no hidden/future feature in deployable non-combat model input;
- `expert_non_combat_v1` remains bootstrap/continuation/fallback, not a
  ground-truth label source;
- battle control remains `oracle_search_v1_highest_mean_s20` where T065 requires
  it;
- source collection is not rerun.

Out of scope:

- changing source scale, split assignment, replay key, quotas, seed sets;
- changing target definition, model topology, optimizer, bootstrap, gates;
- changing supported screen families or action-space semantics;
- natural-A20 or live-game promotion claims;
- generic workflow frameworks or task-numbered production packages;
- recursive provenance/retention discovery or per-stage retention manifests;
- exact shell-token hashes, PID identity, queue identity, or process binding as
  scientific evidence;
- using PR #75 runtime artifacts as authoritative state.

## Frozen T065 Inputs

T075 reuses exactly these retained source artifacts and never recollects or
replaces them:

| Arm | role | Relative path | Bytes | SHA-256 |
|---|---|---|---:|---|
| stochastic | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| expert | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Both must pass the current strict T065 source reader and frozen T065 metadata:
approved spec, config, source arm, driver seed `654001`, seeds `650001..650256`,
256 terminal runs, zero truncations/failures, frozen 16x16 source topology,
action space, battle provenance, and `STS_LIGHTSPEED_INTEGRATION` identity.

Missing, unreadable, identity-invalid, reader-invalid, or metadata-invalid source
is Case D at `SOURCE_REUSE`. No alias search or retention-manifest discovery is
allowed.

## Frozen Cohort Rule

Canonical family order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Seed splits remain:

```text
train       650001..650154
validation  650155..650205
heldout     650206..650256
```

Per-family quotas remain `48/16/16`, so a valid cohort contains exactly 320
states.

Replay equivalence remains exactly:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical candidate JSON uses sorted keys, compact separators,
`ensure_ascii=False`, and `allow_nan=False`.

Member order remains T065:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

T075 group identity is:

```text
group_digest = sha256(
    b"T075-replay-group-v1\n" + canonical_json({
        "family": family,
        "public_state_identity": public_state_identity,
        "ordered_legal_action_identities": ordered_legal_action_identities,
    })
).hexdigest()
```

Selection algorithm:

1. admit every strict selectable mandatory-family candidate from both retained
   source arms and all frozen splits;
2. group globally by the unchanged replay-equivalence key;
3. sort each group by complete `member_order_key`;
4. if two distinct rows have an identical complete member-order key, Case D at
   `SELECTION_REPLAY`; no extra tie breaker exists;
5. otherwise the first member is the sole owner;
6. remove all non-owners before quota selection;
7. retain the owner's seed-derived split;
8. within each `(family, split)` owner bucket, sort by the same member order and
   take exactly the frozen 48/16/16 quota.

Any post-owner bucket shortage is Case D. A valid selected cohort has exact quotas,
unique replay keys, zero cross-split replay overlap, and exact replay of all 320
states. Replay mismatch is Case D and never triggers replacement.

## Frozen Downstream Science

All downstream rules are inherited unchanged from T065. Key frozen identities:

```text
model input: 4634 snapshot + 103 public context = 4737 state; 92 action
continuation seeds:
  train       652001,652002
  validation  652101,652102
  heldout     652201,652202,652203,652204
model seeds: 653001,653002
Stage-5 bootstrap: random.Random(655001), 10000 replicates
Stage-6 fresh seeds: 651001..651256
Stage-6 driver seed: 654002
Stage-6 bootstrap: random.Random(655002), 10000 replicates
```

Stage 5 valid failure is Case C. Stage 6 valid failure is Case B. Fidelity,
completeness, schema, legality, replay, truncation, controller, or information-
regime failure is Case D, not negative science.

## Runtime And Parallelism

Authoritative work uses:

```text
BRANCH = task/T075-architecture-recovery
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-architecture-recovery
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

Every authoritative command runs from `CODE`, with `PYTHONPATH="$NATIVE:$CODE/src"`,
a clean checkout, and exact `HEAD == RUN_HEAD`.

`RUN_HEAD` is frozen only after implementation and executable A01-A24 pass. No
scientific Stage 0-6 execution occurs before `RUN_HEAD` is frozen.

Parallelism:

- `SELECTION_REPLAY`: 16 contiguous shards x 20 selected states, 16 workers;
- `TARGET`: 16 contiguous shards x 20 selected states, 16 workers;
- `TRAIN`: two model seeds, at most two processes, `torch_threads=1` each;
- `GATE`: no simulator sharding;
- `EVAL`: 16 contiguous 16-seed shards per arm, at most 16 simulator workers
  concurrently.

If required resources cannot be established before a stage starts, no stage
outcome is committed. Do not silently reduce the frozen topology.

## Canonical Artifact Identity

```text
ArtifactIdentity = {
  role: non-empty string,
  path: repository-relative POSIX path under artifacts/,
  sha256: 64 lowercase hex,
  size_bytes: integer >= 0
}
```

Equality compares all four fields. Reject `..`, basename-only comparison, case
folding, and alternate-path discovery.

## Minimal Acceptance Model

T075 has exactly one workflow authority. Stage-specific code may validate and
classify scientific results, but only `advance()` changes acceptance state.

Stages:

```text
PREFLIGHT
SOURCE_REUSE
SELECTION_REPLAY
TARGET
TRAIN
GATE
EVAL
```

Terminal cases are `A|B|C|D`.

### StageOutcome

Every committed stage writes one small control record:

```text
schema_id: "t075-stage-outcome-v1"
schema_version: 1
task_id: "T075"
run_head: 40 lowercase hex
stage: Stage
valid: bool
passed: bool
parents: [ArtifactIdentity]
outputs: [ArtifactIdentity]
failure_code: FailureCode | null
```

Unknown top-level keys are rejected. Arrays preserve frozen order. Canonical JSON
is UTF-8, sorted keys, compact separators, `ensure_ascii=False`,
`allow_nan=False`, with one trailing newline.

Invariants:

- `valid=true` => `failure_code=null`;
- `valid=false` => `passed=false`, `outputs=[]`, `failure_code!=null`;
- valid PREFLIGHT/SOURCE_REUSE/SELECTION_REPLAY/TARGET/TRAIN require
  `passed=true`;
- valid GATE/EVAL may have `passed=false` as valid negative science.

FailureCode is exactly:

```text
PREFLIGHT_INVALID
SOURCE_REUSE_INVALID
SELECTION_MEMBER_ORDER_TIE
SELECTION_OWNER_QUOTA_SHORTAGE
SELECTION_REPLAY_INVALID
TARGET_INVALID
TRAIN_INVALID
GATE_EVIDENCE_INVALID
EVAL_EVIDENCE_INVALID
```

Detailed diagnostics belong in stage logs and required PR evidence. They are not
another workflow schema.

### AcceptanceState

```text
CommittedOutcome = {
  outcome: StageOutcome,
  report_identity: ArtifactIdentity(role="stage_outcome")
}

AcceptanceState = {
  run_head,
  committed_outcomes: ordered tuple[CommittedOutcome],
  current_stage: Stage | null,
  terminal_case: A|B|C|D|null,
  terminal_stage: Stage|null
}
```

`artifact_index(state)` contains every committed report identity and every output
identity from every committed valid outcome. No filesystem lookup, hidden registry,
or second lineage validator is required by `advance()`.

Restart reconstructs state by reading stage-outcome files in canonical stage order
and replaying their full StageOutcome values through the same `advance()`.

### Parent And Output Table

| Stage/result | parents | outputs |
|---|---|---|
| PREFLIGHT valid | `[]` | preflight audit |
| PREFLIGHT invalid | `[]` | `[]` |
| SOURCE_REUSE valid | preflight audit + exact stochastic source + exact expert source | source-reuse audit |
| SOURCE_REUSE invalid | preflight audit | `[]` |
| SELECTION_REPLAY valid | source-reuse audit | ownership audit + selected states |
| SELECTION_REPLAY invalid | source-reuse audit | `[]` |
| TARGET valid | preflight audit + selected states | target table |
| TARGET invalid | preflight audit + selected states | `[]` |
| TRAIN valid | target table | checkpoint 653001 + checkpoint 653002 + training-selection summary |
| TRAIN invalid | target table | `[]` |
| GATE valid/invalid | target table + training-selection summary + selected checkpoint | Stage-5 report if valid, else `[]` |
| EVAL valid/invalid | Stage-5 report + training-selection summary + selected checkpoint | Stage-6 report if valid, else `[]` |

Except for the two frozen T065 sources in valid SOURCE_REUSE, every parent must
exist in `artifact_index(state)` in exact row order. Those external sources are
legal only in valid SOURCE_REUSE and must equal the frozen four-field identities.

The GATE/EVAL classifier verifies that checkpoint parent is exactly the checkpoint
selected by the training-selection summary. `advance()` verifies it is a committed
TRAIN checkpoint output; it does not interpret validation MAE.

### Legal Transitions

```text
PREFLIGHT valid+pass        -> SOURCE_REUSE
PREFLIGHT invalid           -> D at PREFLIGHT
SOURCE_REUSE valid+pass     -> SELECTION_REPLAY
SOURCE_REUSE invalid        -> D at SOURCE_REUSE
SELECTION_REPLAY valid+pass -> TARGET
SELECTION_REPLAY invalid    -> D at SELECTION_REPLAY
TARGET valid+pass           -> TRAIN
TARGET invalid              -> D at TARGET
TRAIN valid+pass            -> GATE
TRAIN invalid               -> D at TRAIN
GATE valid+pass             -> EVAL
GATE valid+fail             -> C at GATE
GATE invalid                -> D at GATE
EVAL valid+pass             -> A at EVAL
EVAL valid+fail             -> B at EVAL
EVAL invalid                -> D at EVAL
```

### `advance()` Precedence And Lineage Boundary

```text
advance(state, outcome, report_identity) -> state
```

Apply exactly:

1. reject wrong `run_head`;
2. if stage already committed, identical canonical outcome bytes and identical
   report identity are idempotent; otherwise reject conflicting duplicate;
3. reject any new stage after terminal;
4. require `outcome.stage == current_stage`;
5. require legal valid/passed/failure combination;
6. require frozen report role/path and exact parent/output shape;
7. require every non-external parent to resolve through `artifact_index(state)`;
8. append full outcome + report identity;
9. apply transition table and set next stage or terminal state.

Structural caller-supplied lineage errors are operational rejections before stage
classification. They include wrong/missing/out-of-order parent identities, parent
identity not resolving through `artifact_index(state)`, wrong external-source
identity in a purported valid SOURCE_REUSE outcome, wrong RUN_HEAD, out-of-order
stage, malformed outcome shape, and conflicting duplicate. They are A20 and leave
state unchanged.

Scientific lineage/fidelity failures are different. Once the legitimate TARGET
validator has received structurally valid committed parents, it may discover that
the resolved scientific content violates inherited provenance/schema/public-input
or other frozen T065/T075 fidelity rules. That is A10: commit invalid TARGET with
`failure_code=TARGET_INVALID`, produce Case D, and do not reach TRAIN.

The same distinction applies elsewhere: malformed control identity is operational;
a fidelity failure discovered by the legitimate reached-stage validator is the
stage's committed invalid outcome.

## Transaction And Retry

For a legitimately reached stage:

1. reconstruct canonical state and validate committed structural parents;
2. perform stage work in `ROOT/.tmp/`;
3. validate/classify result using frozen T075/T065 scientific rules;
4. on valid result, atomically promote normative outputs and compute final
   ArtifactIdentity values; on invalid result, promote no normative output;
5. construct final StageOutcome;
6. compute prospective stage-outcome report identity and call `advance()` as a
   pure check;
7. atomically write StageOutcome file; this write is the sole stage commit marker;
8. reconstruct state through the same `advance()` authority;
9. if terminal, materialize terminal report.

If output promotion succeeds but StageOutcome commit does not, those files are
uncommitted and ignored by `artifact_index`; retry from the same committed state
may overwrite them deterministically. A committed StageOutcome is immutable and
is not rerun for a more favorable result.

## Normative Scientific Output Schemas

StageOutcome is the control record. Scientific/fidelity payloads are separate.

### Existing T065 payloads

| T075 output | inherited schema |
|---|---|
| selected states | each row `t065-source-state-v1` |
| target table | `t065-counterfactual-target-table-v1` |
| checkpoints | `t065-non-combat-ranker-checkpoint-v1` |
| Stage-5 report | `t065-heldout-gate-report-v1` |
| Stage-6 report | `t065-complete-run-report-v1` |

Use exact merged T065 serializers/readers at `RECOVERY_BASE`; do not duplicate
those schemas.

### T075 preflight audit

```text
schema_id: "t075-preflight-audit-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
recovery_base: git_commit
t065_approved_spec: git_commit
sts_lightspeed_integration: git_commit
model_input_schema_id: "non-combat-model-input-v1"
state_dim: 4737
action_dim: 92
checks_passed: [
  "runtime_imports",
  "simulator_identity",
  "checkpoint_roundtrip",
  "frozen_controller_action_space",
  "model_input_schema",
  "public_input_firewall",
  "torch_runtime"
]
```

Unknown keys rejected. Exists only for valid PREFLIGHT.

### T075 source-reuse audit

```text
schema_id: "t075-source-reuse-audit-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
sources: [ArtifactIdentity, ArtifactIdentity]  # stochastic, expert
strict_reader_passed: true
metadata_passed: true
```

Unknown keys rejected. Exists only for valid SOURCE_REUSE.

### T075 ownership audit

```text
schema_id: "t075-ownership-audit-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
strategy_id: "leakage-safe-global-owner-v1"
replay_group_domain: "T075-replay-group-v1"
raw_candidate_count: nonneg_int
group_count: nonneg_int
cross_split_group_count: nonneg_int
excluded_non_owner_count: nonneg_int
available_after_ownership: [FamilySplitCount]
groups: [OwnershipGroup]

FamilySplitCount = {
  family: Family,
  split: train|validation|heldout,
  count: nonneg_int
}
OwnershipGroup = {
  group_digest: sha256,
  family: Family,
  members: [OwnershipMember]
}
OwnershipMember = {
  source_arm: stochastic_non_combat_v1|expert_non_combat_v1,
  simulator_seed: int,
  split: train|validation|heldout,
  selection_digest: sha256,
  candidate_sha256: sha256,
  owner: bool
}
```

`available_after_ownership` is family order then train/validation/heldout. Groups
sort by `group_digest`; members sort by complete member-order key. Valid groups
have exactly one owner. Unknown keys at every T075-owned record level rejected.

### T075 training-selection summary

```text
schema_id: "t075-training-selection-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
model_seeds: [653001, 653002]
checkpoints: [ArtifactIdentity, ArtifactIdentity]
validation_mae: [finite number, finite number]
selected_model_seed: 653001|653002
selected_checkpoint: ArtifactIdentity
```

Checkpoint arrays are model-seed order. Lower validation MAE wins; exact tie to
seed 653001. Unknown keys rejected.

## Terminal Decision

Terminal report is derived only from canonical AcceptanceState, never recomputed
from raw metrics.

```text
schema_id: "t075-terminal-decision-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
terminal_case: A|B|C|D
terminal_stage: Stage
stage_outcomes: [ArtifactIdentity]
promotion: "experimental_public_with_expert_fallback"|"no_promotion"
recommendation_code: "review_joint_policy"|"narrow_transfer_followup"|"close_v1"|"repair_same_experiment"
```

Unknown keys rejected. `stage_outcomes` are committed StageOutcome report
identities in canonical order.

Mapping:

- A: experimental public learned controller with expert fallback;
  `review_joint_policy`; no natural-A20/live promotion claim.
- B: no promotion; `narrow_transfer_followup`.
- C: no promotion; Stage 6 absent; `close_v1`; a later Planner may separately
  propose at most one target/model diagnostic.
- D: no promotion/policy conclusion; `repair_same_experiment`; all later
  scientific stages absent.

The first committed terminal state, including Case D produced by an invalid
StageOutcome, is immutable. If terminal materialization is interrupted after the
terminal-producing StageOutcome commit, restart reconstructs state and writes the
same terminal report. A conflicting existing terminal report is an operational
integrity failure and cannot reinterpret science.

## Final Retention

T075 uses exactly one lightweight final retention manifest. It is not a per-stage
manifest graph and performs no recursive discovery.

Exact schema:

```text
schema_id: "t075-retention-v1"
schema_version: 1
task_id: "T075"
run_head: git_commit
terminal_case: A|B|C|D
terminal_report: ArtifactIdentity
retention_owner: "T075"
retention_reason: non-empty string
possible_downstream_consumers: [non-empty string]
delection_condition_code: "after_merge_no_consumer_or_reproduction_hold"
entries: [RetentionEntry]

RetentionEntry = {
  artifact: ArtifactIdentity,
  provenance: {
    source_kind: "reused_t065"|"t075_committed_output",
    producer_task: non-empty string,
    producer_stage: non-empty string,
    producer_git_commit: git_commit
  },
  regeneration_commands: [non-empty string],
  compatibility_requirements: [non-empty string],
  retention_reason: non-empty string,
  possible_downstream_consumers: [non-empty string]
}
```

Unknown keys are rejected at both manifest and entry/provenance levels. `entries`
contains, in order:

1. exact stochastic T065 source;
2. exact expert T065 source;
3. every committed T075 StageOutcome report in stage order;
4. every normative output from committed valid T075 stages in stage/output order;
5. terminal report.

For the two reused T065 sources, `producer_task="T065"`, producer commit is the
validated T065 producer provenance, and `regeneration_commands` records the
historical T065 Stage-1 producer commands. The command forms are the merged T065
neutral command surface:

```text
$PY -m sts_combat_rl.commands.non_combat_learning collect \
  --arm stochastic_non_combat_v1 --output <stable-source-path> \
  --seed-start 650001 --seed-end 650256 --sim-seed 1 --ascension 20 \
  --preflight <validated-t065-preflight>

$PY -m sts_combat_rl.commands.non_combat_learning collect \
  --arm expert_non_combat_v1 --output <stable-source-path> \
  --seed-start 650001 --seed-end 650256 --sim-seed 1 --ascension 20 \
  --preflight <validated-t065-preflight>
```

These commands are provenance only. T075 never executes them and never authorizes
source recollection.

For T075-produced entries, `regeneration_commands` records the exact command(s)
actually used on `RUN_HEAD`; command strings are provenance, not scientific
identity, so shell-token equality is not an acceptance check. Compatibility
requirements must state the relevant T065/T075 schema IDs, `RUN_HEAD`,
`STS_LIGHTSPEED_INTEGRATION` where simulator-dependent, and pinned model-input
contract where applicable.

`possible_downstream_consumers` must explicitly name known consumers or contain
exactly `"none currently approved"`; it must not be omitted. Large T075 outputs
may be deleted only after terminal/retention merge, no approved consumer remains,
and no reproduction hold remains. Compact outcome, terminal, and retention
records remain.

The first committed terminal state is immutable even if retention materialization
or deletion bookkeeping later fails. Such a finalization failure is operational
and cannot rewrite A/B/C/D.

## Durable Paths

Under `ROOT`:

```text
outcomes/00-preflight.json
outcomes/01-source-reuse.json
outcomes/02-selection-replay.json
outcomes/03-target.json
outcomes/04-train.json
outcomes/05-gate.json
outcomes/06-eval.json                 # only if reached
preflight-audit.json                  # valid PREFLIGHT only
source-reuse-audit.json               # valid SOURCE_REUSE only
ownership-audit.json                  # valid SELECTION_REPLAY only
selected-states.jsonl                 # valid SELECTION_REPLAY only
target-table.json                     # valid TARGET only
checkpoints/                           # valid TRAIN only
training-selection.json               # valid TRAIN only
heldout-gate-report.json              # valid GATE only
complete-run-report.json              # valid EVAL only
terminal-decision.json
retention.json
.tmp/
```

Normative paths are fixed. Temporary files are never semantic parents.

## Command Surface

Use neutral `sts_combat_rl.commands.non_combat_learning`. T075 may add bounded
stage adapters there but no T075-numbered package, workflow framework, or legacy
flat-CLI route.

Reference semantic operations:

| stage | operation | required semantic inputs |
|---|---|---|
| PREFLIGHT | `preflight` | RUN_HEAD, runtime/simulator/model-input contract |
| SOURCE_REUSE | `validate-reuse` | exact two frozen T065 sources, preflight audit |
| SELECTION_REPLAY | `select` | exact sources, source-reuse audit, ownership strategy, 16x20 replay plan |
| TARGET | `target` | selected states, preflight audit, 16x20 target plan |
| TRAIN | `train` | target table, frozen T065 training config |
| GATE | `gate` | target table, training selection/checkpoints |
| EVAL | `eval` | valid Stage-5 report, selected checkpoint, 16x16-per-arm plan |
| finalization | `finalize` | committed outcome files, terminal report, retention output |

Exact shell quoting/token text is not semantic identity. Each operation exposes
explicit paths and RUN_HEAD and fails before stage work for wrong checkout,
wrong RUN_HEAD, or arbitrary input path.

Required local gates use pinned interpreter:

```bash
$PY -m pytest -q tests/test_t075_acceptance.py
$PY -m pytest -q tests/test_non_combat_learning.py
$PY -m pytest -q
$PY -m compileall -q src tests
$PY -m ruff check src tests
$PY -m ruff format --check src tests
$PY -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
$PY -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
git diff --check
```

Before real simulator evidence, run repository pinned
`verify_lightspeed_source.sh` gate.

## Normative Acceptance Matrix

The matrix freezes semantics before implementation. The executable suite is a
mechanical encoding after `SPEC APPROVED`.

| ID | Scenario | Required result |
|---|---|---|
| A01 | both exact frozen sources pass identity/reader/metadata | SOURCE_REUSE valid; source-reuse audit records exact identities |
| A02 | either frozen source missing/unreadable/identity/reader/metadata invalid | committed invalid SOURCE_REUSE; D; no source-reuse audit |
| A03 | raw replay-equivalent candidates cross seed splits | deterministic global owner; not itself failure |
| A04 | distinct rows have identical complete member-order key | invalid SELECTION_REPLAY with `SELECTION_MEMBER_ORDER_TIE`; D |
| A05 | post-owner family/split bucket below quota | invalid SELECTION_REPLAY with `SELECTION_OWNER_QUOTA_SHORTAGE`; D |
| A06 | provisional selected duplicate/cross-split replay overlap | invalid SELECTION_REPLAY with `SELECTION_REPLAY_INVALID`; D |
| A07 | exact 320 cohort, ownership audit, exact replay under 16x20/16-worker plan | valid SELECTION_REPLAY; ownership audit + selected states committed |
| A08 | one selected replay mismatch | invalid SELECTION_REPLAY with `SELECTION_REPLAY_INVALID`; D; no replacement/output promotion |
| A09 | target missing/duplicate/nonfinite/wrong action order/continuation seed | invalid TARGET with `TARGET_INVALID`; D; no target table |
| A10 | structurally valid TARGET parents resolve, then legitimate TARGET validator discovers scientific provenance/schema/public-input/fidelity mismatch | invalid TARGET with `TARGET_INVALID`; D; TRAIN absent |
| A11 | prospective data exists but StageOutcome commit interrupted | stage uncommitted; same stage retryable; no terminal |
| A12 | valid TARGET and valid TRAIN | GATE reached; two checkpoints + training-selection committed |
| A13 | valid Stage-5 pass | GATE valid+pass; EVAL reached |
| A14 | valid Stage-5 fail | GATE valid+fail; terminal C; EVAL absent; v1 closed |
| A15 | malformed/incomplete/nonfinite/schema-invalid Stage-5 evidence | GATE invalid with `GATE_EVIDENCE_INVALID`; D |
| A16 | valid Stage-6 pass | EVAL valid+pass; terminal A |
| A17 | valid Stage-6 fail | EVAL valid+fail; terminal B |
| A18 | missing/truncated/controller/schema/nonfinite Stage-6 evidence | EVAL invalid with `EVAL_EVIDENCE_INVALID`; D |
| A19 | initial state | PREFLIGHT current; empty committed list; no terminal |
| A20 | wrong RUN_HEAD/out-of-order/malformed control shape, structurally wrong/missing/unresolved/out-of-order parent identity, or conflicting duplicate | operational reject before stage classification; state unchanged |
| A21 | interruption before StageOutcome atomic commit | no committed stage/terminal; retry from same state |
| A22 | identical already-committed StageOutcome/report retried or first committed terminal (including D) already materialized | idempotent state; no science rerun; terminal immutable |
| A23 | deployable input includes behavior/expert/target/hidden/future information | invalid TARGET with `TARGET_INVALID`; D |
| A24 | helper/finalizer disagrees with canonical state, or retention fails after terminal | `IMPLEMENTATION_BUG`/operational failure; first committed scientific terminal unchanged |

Any materially new semantic scenario not uniquely resolved by this contract is a
`CONTRACT_GAP`. Do not create A25 locally.

## Authorization And Implementation Order

1. Planner freezes this normative contract and A01-A24 matrix.
2. Maintainer performs execution-readiness review.
3. Maintainer publishes exact-head `SPEC APPROVED` /
   `implementation_authorized=true`.
4. Implementer first writes the implementation-independent executable A01-A24
   suite and fixtures. Production helpers must not generate expected values.
5. If test encoding exposes semantic ambiguity, stop as `CONTRACT_GAP`; Planner
   revises contract and Maintainer reauthorizes new exact head.
6. If matrix encodes without semantic invention, Implementer performs one bounded
   production pass against it.
7. Maintainer runs A01-A24 and required local gates and fixes only
   `IMPLEMENTATION_BUG` findings.
8. Maintainer freezes one clean exact implementation `RUN_HEAD`.
9. Authoritative T075 scientific stages execute only on that RUN_HEAD.
10. One terminal A/B/C/D and one retention record are materialized.
11. Planner performs exact-head scientific/architecture acceptance.
12. Maintainer performs exact-head implementation/operational acceptance and
    merges only when both pass.

`SPEC APPROVED` authorizes implementation work; test-only A01-A24 is the first
implementation step.

## Required PR Evidence

Before final acceptance PR #77 must report:

1. exact recovery base, approved contract head, implementation RUN_HEAD, and
   `STS_LIGHTSPEED_INTEGRATION`;
2. proof PR #75 runtime artifacts were not used as authoritative state;
3. exact two T065 source identities plus strict reader/metadata result;
4. raw candidate/group/cross-split/non-owner counts and post-owner availability;
5. selected count/quotas/replay result and ownership-audit identity;
6. TARGET completeness/fidelity result and target-table identity if valid;
7. TRAIN model seeds, validation MAEs, checkpoint identities, selected checkpoint;
8. Stage-5 predicates/result and Stage-6 evidence/result if reached;
9. shard/worker/range/wall-clock evidence for expensive stages;
10. required local/simulator verification results and any deviation;
11. terminal case/stage/promotion/recommendation and terminal identity;
12. final retention-manifest identity, retention owner/reason, every retained
    artifact hash/size, regeneration commands, compatibility requirements,
    possible downstream consumers, and deletion condition;
13. every `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION`
    encountered and its disposition.

This is reporting scope, not a second scientific gate.

## Salvage And Architecture Guardrails

May be reused from merged main / T065:

- strict T065 serializers/readers and scientific reducers;
- source replay/target/training/Stage-5/Stage-6 primitives that preserve frozen
  T065 semantics;
- generic spawn/process batching primitives if independent of PR #75 control
  plane;
- independent fixtures that encode frozen science rather than private helper
  behavior.

Do not mechanically cherry-pick PR #75 task-specific orchestration, validator
registries, recursive retention/provenance discovery, command-token proof,
PID/process proof, or tests that reconstruct contract semantics from private
helpers.

One canonical `advance()` owns transition/terminal semantics. One
`artifact_index(state)` owns committed T075 artifact lookup. Stage validators own
scientific classification only. Finalization derives terminal/retention from
canonical state and does not recompute scientific gates.

## Escalation And Final Acceptance

Classification:

- `IMPLEMENTATION_BUG`: frozen contract uniquely determines correct behavior;
- `CONTRACT_GAP`: meaningful case is not uniquely determined here;
- `ARCHITECTURE_ESCALATION`: repeated/new cross-module semantic classes,
  duplicated acceptance authority, private-helper-coupled acceptance, or a new
  generic control plane appears.

After one corrective implementation pass, another new cross-module problem class
is presumed escalation unless it is clearly an ordinary A01-A24 violation.

Planner final acceptance checks exact RUN_HEAD for:

- only global replay ownership changed scientifically;
- T065 information regime and downstream science remain frozen;
- A/B/C/D retain T065 meaning;
- state/lineage/terminal semantics have one authority;
- invalid science is not confused with valid negative science;
- no PR #75 control-plane architecture was recreated.

Maintainer final acceptance separately checks exact RUN_HEAD implementation,
A01-A24, required gates, runtime artifacts, retention completeness, branch hygiene,
and merge readiness. Both acceptances are required.