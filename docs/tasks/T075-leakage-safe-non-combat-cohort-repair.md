# T075: Leakage-Safe Non-Combat Cohort Repair

## Architecture Recovery Declaration

This document is the single normative Planner contract for the T075 recovery line.
It supersedes the unmerged T075 specification/implementation history on PR #75 for
all future implementation and acceptance decisions.

PR #75 is retained only as an architecture-failure audit record. Its production
orchestration, task-specific lifecycle validators, exact-command matching,
per-stage retention machinery, acceptance helpers, and runtime artifacts are not
accepted project state and must not be used as the recovery implementation
baseline.

Architecture recovery base:

`bc9a6790f36ff036f90dc7f03ba0ff026a16788d`

Historical references:

- accepted T065 result: merged task T065;
- rejected T075 implementation/audit line: PR #75;
- previously approved T075 proposal: `e204c5d28cc0bee8013853e8680e8966f5c930a8`.

The recovery keeps the T075 scientific experiment and replaces the rejected
control-plane architecture with one canonical acceptance authority, transactional
stage commits, a small typed serialization contract, minimal semantic lineage,
and one frozen scientific `RUN_HEAD`.

## Objective

Repair the single cohort-partition defect exposed by T065 Case D and, only if the
repaired cohort is valid, continue the otherwise unchanged T065 learned
non-combat experiment.

T065 remains `DONE` with its valid Case D. T075 does not reinterpret, overwrite,
or weaken that result.

The only new scientific rule in T075 is:

> replay-equivalent candidates are assigned one deterministic global owner before
> the unchanged per-family/per-split quota selection.

Everything downstream of a valid selected cohort remains T065 science unless this
document explicitly says otherwise.

## Dependencies, Lifecycle, And Frozen Upstream Identities

T075 depends on:

- T033 public-context model-input encoder contract;
- T040 `expert_non_combat_v1`;
- T061 reachability-bottleneck evidence;
- T064 simulator-generated later-act curriculum result;
- T065 learned non-combat workflow, strict readers, retained Stage-1 evidence, and
  valid Case-D result;
- T071 simplified experiment execution/reuse convention;
- T074 core decision/policy boundary repair.

The proposed lifecycle entry is `T075 | DRAFT` until the Main Maintainer publishes
exact-head `SPEC APPROVED` with `implementation_authorized=true`.

Frozen upstream identities:

```text
T065_APPROVED_SPEC = a13c92a66b4d9ad9f6a730293cadc8d66b4a699c
STS_LIGHTSPEED_INTEGRATION = fee272f1ae21c283ad2161f55293cfe6d714134a
```

A mismatch in the current T065 scientific contract or pinned `sts_lightspeed`
integration blocks readiness. If such a mismatch is observed by the frozen T075
PREFLIGHT under the correct `RUN_HEAD`, PREFLIGHT commits an invalid outcome and
T075 ends Case D.

T034, T063, and T066 are outside T075.

## Scientific And Information-Regime Boundary

T075 remains inside the repository training paradigm:

- no human trajectories or human action labels;
- no expert-policy imitation target;
- no hidden/future feature in the deployable non-combat model input;
- `expert_non_combat_v1` is a frozen bootstrap/continuation controller, not
  ground-truth supervision;
- selected states, counterfactual targets, model training, and evaluation are
  simulator generated.

Any implementation change that alters the public model input, replay identity,
continuation policy, target definition, model topology, training hyperparameters,
or Stage-5/Stage-6 scientific gates is a `CONTRACT_GAP`, not an implementation
fix.

## Frozen Runtime And Execution Checkout

The recovery implementation and authoritative scientific execution use exactly:

```text
BRANCH = task/T075-architecture-recovery
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-architecture-recovery
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

All commands run from `CODE` with:

```bash
cd "$CODE"
export PYTHONPATH="$NATIVE:$CODE/src"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain)"
```

No authoritative scientific stage runs until production implementation and the
implementation-independent A01--A24 acceptance boundary pass and the Maintainer
freezes one exact implementation commit as `RUN_HEAD`.

For every authoritative stage:

```bash
test "$(git rev-parse HEAD)" = "$RUN_HEAD"
test -z "$(git status --porcelain)"
```

Wrong branch, dirty checkout, missing `RUN_HEAD`, or `HEAD != RUN_HEAD` is an
invocation failure before scientific execution. No StageOutcome is committed and
no Case A/B/C/D is created.

If production code changes after authoritative execution starts, the old
`RUN_HEAD` is retired. The Maintainer identifies the earliest semantically
affected stage, refreezes a new `RUN_HEAD` only after the acceptance boundary
passes again, and reruns the affected stage and all downstream stages. PR #75
runtime outputs are never authoritative recovery evidence.

## Frozen T065 Scientific Inputs

T075 reuses exactly these two retained T065 raw source files and never recollects
them:

| Arm | Relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Each file must pass the current strict T065 source reader and match:

- source schema/version required by merged T065;
- `approved_spec_commit == T065_APPROVED_SPEC`;
- exact current `T065ExperimentConfig().to_dict()`;
- expected source arm;
- source driver seed `654001`;
- source seeds exactly `650001..650256`;
- requested/terminal run count `256`;
- truncated run count `0`;
- failed run count `0`;
- 16 ordered shards x 16 seeds and effective worker count 16;
- frozen action space;
- battle provenance `oracle_search_v1_highest_mean_s20`;
- simulator integration `STS_LIGHTSPEED_INTEGRATION`;
- no source-level problems.

The exact file identities above are sufficient T075 input identity. T075 must not
rediscover them through retention manifests, historical aliases, basename search,
or recursive provenance traversal.

If either file is missing, unreadable, hash/size invalid, or fails strict metadata
validation, SOURCE_REUSE commits invalid and T075 ends Case D.

Source recollection, source replacement, alternate aliases, and best-effort input
discovery are forbidden.

### Source and split constants

```text
player = IRONCLAD
ascension = 20
source seeds = 650001..650256
source driver seed = 654001
source arms = stochastic_non_combat_v1, expert_non_combat_v1
battle controller = oracle_search_v1_highest_mean_s20
```

Seed-derived splits:

```text
train      = 650001..650154
validation = 650155..650205
heldout    = 650206..650256
```

No simulator seed may change split.

Canonical family order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas:

```text
train = 48
validation = 16
heldout = 16
```

A valid cohort has exactly 320 selected states. Other screens remain fallback-only
and are not selectable training states.

### Public model input

Use `non-combat-model-input-v1` exactly:

```text
tactical snapshot dimension = 4634
public context dimension = 103
state dimension = 4737
legal-action dimension = 92
```

No expert/behavior/target/outcome/hidden/future feature is permitted. Population
normalization is training-split-only CPU float32; std is clamped to at least 1.0
and checkpointed unchanged.

## T075 Scientific Primitive: Global Ownership

Selectable candidates must:

- pass the strict `t065-source-state-v1` reader;
- come from a problem-free terminal source run;
- belong to a mandatory family;
- retain their simulator-seed-derived split and source provenance;
- pass existing T065 public/model/action/replay validation.

Malformed or provenance-invalid rows fail closed. Nonterminal or truncated rows
remain source evidence but are not selectable.

Replay equivalence remains exactly:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical candidate member order remains T065:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Replay-group audit identity:

```text
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
group_digest = sha256(
    T075_GROUP_DOMAIN + canonical_json({
        "family": family,
        "public_state_identity": public_state_identity,
        "ordered_legal_action_identities": ordered_legal_action_identities,
    })
).hexdigest()
```

Scientific digest JSON uses UTF-8, sorted keys, compact separators `(',', ':')`,
`ensure_ascii=False`, and `allow_nan=False`.

Ownership algorithm:

1. admit all selectable candidates from both source arms and every frozen split;
2. group globally by the unchanged replay-equivalence key;
3. sort each group by `member_order_key`;
4. if two distinct source rows have an identical complete `member_order_key`,
   fail Case D at SELECTION_REPLAY; do not invent another tie breaker;
5. otherwise the first member is the sole owner;
6. exclude all non-owners before quota selection;
7. keep the owner's seed-derived split;
8. inside each `(family, split)` owner bucket, sort by the same member order and
   take exactly 48/16/16.

If any owner bucket is below quota, T075 ends Case D. There is no recollection,
scale increase, split reassignment, balancing, target-aware selection, strategic
quality filter, manual replacement, or replay-key change.

A valid selected cohort has exactly 320 states, exact family/split quotas,
globally unique replay-equivalence keys, zero cross-split replay overlap, zero
seed-split leakage, exact replay of all selected public/model states and ordered
legal actions, and zero replacement after replay failure.

## Unchanged Downstream Science

### Counterfactual targets

Every selected state evaluates every eligible legal action from the same restored
checkpoint. Continuation controller is `expert_non_combat_v1`.

Continuation seeds:

```text
train      = (652001, 652002)
validation = (652101, 652102)
heldout    = (652201, 652202, 652203, 652204)
```

Target:

`q_floor = mean(max(0, terminal_floor - source_floor))`

No action subsampling, replacement, alternate reward, failed-branch dropping, or
hidden-future resampling is allowed.

### Ranker

Model seeds: `(653001, 653002)`.

Topology:

```text
state 4737 -> Linear(4737,64) -> ReLU -> Linear(64,64) -> ReLU
action 92 -> Linear(92,64) -> ReLU -> Linear(64,64) -> ReLU
concat 128 -> Linear(128,64) -> ReLU -> Linear(64,1)
```

Training remains T065:

- CPU PyTorch;
- default `nn.Linear` initialization after `torch.manual_seed(model_seed)`;
- Huber delta 1;
- Adam lr `1e-3`;
- 1500 steps;
- minibatch 64 sampled with replacement by the frozen generator;
- gradient clip 10;
- `torch_threads=1`;
- no early stopping or architecture sweep;
- validation `q_floor` MAE selects the checkpoint;
- exact MAE tie chooses the lower model seed.

### Stage-5 held-out gate

Use the 64 heldout states. A valid Stage-5 report passes only if all are true:

1. aggregate mean paired `q_floor(model)-q_floor(expert) > 0`;
2. median paired delta `>= 0`;
3. at least 3 of 4 family mean deltas `>= 0`;
4. 10,000-stratified-bootstrap `p_positive >= 0.90` using
   `random.Random(655001)`;
5. non-selected model-seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violation.

A valid failure is Case C and EVAL is skipped.

### Conditional Stage-6 complete-run gate

Run only after a valid Stage-5 pass.

```text
fresh seeds = 651001..651256
driver/fallback seed = 654002
arm order = stochastic, expert, learned
shards = 16 x 16 seeds per arm
required terminal runs = 768
bootstrap = 10,000 matched-seed resamples, random.Random(655002)
coverage = L/D >= 0.60 and F/M <= 0.01 with D != 0 and M != 0
```

The learned arm uses learned policy on mandatory families and expert fallback
elsewhere. T065 D/L/M/F definitions are unchanged.

A valid Stage-6 report passes only if:

1. matched mean terminal-floor delta `> 0`;
2. bootstrap `p_positive >= 0.80`;
3. learned Act-2 entry count `>=` expert;
4. zero controller errors and unreported truncations;
5. coverage passes;
6. learned Act-2 count `>` expert or `p_positive >= 0.95`.

## Canonical Acceptance Model

T075 has exactly one production-side acceptance authority. CLI handlers, artifact
readers, stage adapters, persistence code, and finalization code must not
implement independent transition predicates.

### Canonical types

```text
Stage =
  PREFLIGHT
  SOURCE_REUSE
  SELECTION_REPLAY
  TARGET
  TRAIN
  GATE
  EVAL

TerminalCase = A | B | C | D

ArtifactIdentity =
  role
  path
  sha256
  size_bytes

StageOutcome =
  schema_id
  schema_version
  task_id
  run_head
  stage
  valid
  passed
  parents
  outputs
  evidence
  problems

CommittedOutcome =
  stage
  report_identity

AcceptanceState =
  run_head
  committed_outcomes
  current_stage or none
  terminal_case or none
  terminal_stage or none
```

`committed_outcomes` is the ordered ledger of committed StageOutcome report
identities. It is derived from durable stage-report files; there is no separate
mutable workflow-state file.

There must be one pure or effectively pure transition authority equivalent to:

```text
advance(AcceptanceState, StageOutcome) -> AcceptanceState
```

`outcome_identity(outcome)` is the deterministic `ArtifactIdentity` obtained by
canonical serialization of the outcome at that stage's frozen report path. Its
`sha256` is therefore the identity used for duplicate comparison.

### Initial state

```text
run_head = RUN_HEAD
committed_outcomes = ()
current_stage = PREFLIGHT
terminal_case = None
terminal_stage = None
```

### Legal scientific transitions

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

For PREFLIGHT, SOURCE_REUSE, SELECTION_REPLAY, TARGET, and TRAIN,
`valid=true, passed=false` is illegal.

Terminal meanings:

```text
A = valid positive Stage-6 transfer result
B = valid Stage-6 negative result
C = valid Stage-5 negative result
D = invalid experiment / frozen-fidelity failure
```

Poor learned-policy performance alone produces B or C, never D.

### Transition precedence and duplicate semantics

For every candidate StageOutcome, canonical `advance` applies this order:

1. `outcome.run_head` must equal `state.run_head`; otherwise reject
   operationally with state unchanged.
2. Compute `candidate_identity = outcome_identity(outcome)`. If the ledger already
   contains the same `outcome.stage`, perform duplicate handling **before** any
   current-stage or terminal rejection:
   - if `candidate_identity == committed.report_identity`, return the existing
     state idempotently and do not rerun science;
   - otherwise reject as a conflicting duplicate; state and terminal are
     unchanged.
3. If `state.terminal_case` is not null, reject any new uncommitted stage;
   terminal state is immutable.
4. `outcome.stage` must equal `state.current_stage`; otherwise reject as
   out-of-order with state unchanged.
5. Validate the stage's legal `(valid, passed)` combination and exact parent
   identities. Invocation mistakes that never reach a legitimate stage adapter
   do not become StageOutcomes.
6. Apply exactly the legal transition table above. Append the committed outcome
   identity to the ledger. If terminal, set both `terminal_case` and
   `terminal_stage` and set `current_stage=None`; otherwise advance to the next
   stage.

This precedence makes idempotent retry distinguishable from an out-of-order or
conflicting duplicate after `current_stage` has advanced.

### Edge and restart semantics

- Wrong branch, dirty checkout, wrong `RUN_HEAD`, malformed CLI invocation, or an
  arbitrary wrong input path rejected before a legitimate stage begins is an
  operational invocation error: no StageOutcome and no scientific terminal.
- Interruption before atomic StageOutcome report commit leaves the stage
  uncommitted and retryable from the same committed parents and `RUN_HEAD`.
- Once an invalid StageOutcome is atomically committed, it is scientific/fidelity
  evidence. `advance` yields Case D and that stage is not rerun to seek a better
  result.
- A legitimately reached stage whose canonical parent artifact no longer matches
  its recorded `ArtifactIdentity`, or whose required scientific lineage fails,
  commits invalid and therefore D at that stage.
- If a terminal-producing StageOutcome is committed but terminal-report writing is
  interrupted, restart reconstructs state by replaying the committed ledger and
  materializes exactly the same A/B/C/D and `terminal_stage`; no science reruns.
- A terminal report inconsistent with the committed outcome ledger is an
  operational integrity failure. It must not overwrite or reinterpret the
  canonical terminal state.
- Final retention failure after terminal commit is operational failure; terminal
  A/B/C/D is unchanged.

## Transactional Stage Commit

Every stage follows one transaction shape:

1. validate canonical state, checkout, `RUN_HEAD`, and committed parents;
2. write expensive/intermediate data only under `ROOT/.tmp/` or an equivalent
   non-committed location;
3. run stage-specific completeness/fidelity validation;
4. construct a complete valid or invalid StageOutcome;
5. validate the prospective transition through canonical `advance`;
6. for a successful stage, promote validated durable data to frozen paths and
   compute output identities;
7. atomically write the StageOutcome report last at its frozen report path;
8. reconstruct/advance durable state from the committed report;
9. if the transition is terminal, atomically materialize the single terminal
   report from that canonical state.

The StageOutcome report is the stage commit marker. Durable-looking data without a
matching committed StageOutcome is uncommitted and cannot be a parent.

A process interruption before step 7 is operationally incomplete and retryable.
Do not preserve every partial PID, worker return, queue message, or temporary file
as scientific evidence.

### TARGET / logical Stage-3 barrier

Logical Stage 3 is a mandatory commit barrier inside TARGET; it is not a separate
execution stage.

Target generation remains under a temporary path until the persisted target
payload is reopened and these checks run in this exact order:

1. `strict_target_reader`
2. `target_completeness`
3. `selected_state_lineage`
4. `simulator_and_preflight_lineage`
5. `model_input_schema`
6. `state_action_dimensions`
7. `finite_numeric_values`
8. `legal_action_order`
9. `continuation_seed_contract`
10. `public_input_firewall`

If all checks pass, the target table is promoted to its frozen path and TARGET
atomically commits `valid=true, passed=true` with the target-table identity in
`outputs`.

If any completed check fails, TARGET constructs and atomically writes the same
`stage2-validation.json` StageOutcome with:

```text
valid = false
passed = false
outputs = []
stage3_barrier_passed = false
problems = non-empty
```

That invalid report is a committed StageOutcome; canonical `advance` yields Case D
at TARGET and TRAIN is forbidden. The failed target payload remains only under the
uncommitted temporary area and is not a canonical parent.

If execution is interrupted before the invalid or valid `stage2-validation.json`
atomic commit, TARGET remains uncommitted, no terminal exists, and retry is
allowed. This is distinct from a completed barrier failure.

## Exact Serialization Contract

This section freezes only data that A01--A24 or artifact lineage actually depend
on. Process-manager internals and arbitrary diagnostic decoration are deliberately
excluded. Adding a new acceptance-relevant field or meaning is a `CONTRACT_GAP`;
adding non-normative logs outside these artifacts is implementation freedom.

### JSON scalar rules

All T075 JSON control/report artifacts use UTF-8 canonical JSON:

```text
sort_keys=True
separators=(',', ':')
ensure_ascii=False
allow_nan=False
one trailing newline
```

Types:

```text
string = JSON string
bool = true | false
int = JSON integer (not bool)
nonneg_int = int >= 0
number = finite JSON integer or float
sha256 = lowercase 64-character hexadecimal string
StageName = PREFLIGHT | SOURCE_REUSE | SELECTION_REPLAY | TARGET | TRAIN | GATE | EVAL
Family = MAP_SCREEN | REST_ROOM | REWARDS | TREASURE_ROOM
Split = train | validation | heldout
Arm = stochastic | expert | learned
SourceArm = stochastic_non_combat_v1 | expert_non_combat_v1
Status = passed | failed
```

Unknown top-level keys in the v1 T075 report schemas below are rejected. Evidence
objects have exactly the fields frozen for that stage. Existing unchanged T065
scientific payloads keep their merged strict T065 schemas and are not duplicated
inside T075 reports.

### Shared serialized records

`ArtifactIdentity` has exactly:

```json
{"role":"string","path":"string","sha256":"sha256","size_bytes":0}
```

Constraints:

- `path` is repository-relative POSIX under `artifacts/`;
- normalize backslashes to `/`, remove `.` and one leading `./`, reject `..`;
- paths are case-sensitive;
- basename-only matching is forbidden;
- `size_bytes` is `nonneg_int`.

`CheckRecord`:

```json
{"name":"string","status":"passed|failed","counts":{"key":0},"problems":["string"]}
```

`counts` is a JSON object from string to `nonneg_int`; its keys are diagnostic and
not transition predicates unless a stage schema below names them explicitly.

`RangeRecord`:

```json
{"shard_index":0,"start":0,"end":19,"count":20,"wall_clock_seconds":0.0}
```

`PredicateRecord`:

```json
{"name":"string","passed":true}
```

`FamilyValue`:

```json
{"family":"MAP_SCREEN","value":0.0}
```

`FamilySplitCount`:

```json
{"family":"MAP_SCREEN","split":"train","count":0}
```

`SplitCount`:

```json
{"split":"train","count":0}
```

`HistogramBin`:

```json
{"group_size":1,"group_count":0}
```

`SourceRecord`:

```json
{
  "arm":"stochastic_non_combat_v1",
  "artifact":{"role":"string","path":"string","sha256":"sha256","size_bytes":0},
  "strict_reader_passed":true,
  "metadata_passed":true,
  "seed_start":650001,
  "seed_end":650256,
  "requested_run_count":256,
  "terminal_run_count":256,
  "truncated_run_count":0,
  "failed_run_count":0,
  "shard_count":16,
  "worker_count":16,
  "controller":"oracle_search_v1_highest_mean_s20",
  "approved_spec_commit":"sha256",
  "sts_lightspeed_commit":"sha256"
}
```

`OwnershipMember`:

```json
{
  "source_arm":"stochastic_non_combat_v1",
  "simulator_seed":650001,
  "split":"train",
  "family":"MAP_SCREEN",
  "selection_digest":"sha256",
  "candidate_sha256":"sha256",
  "owner":true
}
```

`candidate_sha256 = sha256(canonical_candidate_json_bytes)` is audit identity only
and is never an ownership tie breaker.

`OwnershipGroup`:

```json
{
  "group_digest":"sha256",
  "family":"MAP_SCREEN",
  "member_count":1,
  "cross_split":false,
  "members":[OwnershipMember]
}
```

Members are ordered by the complete frozen `member_order_key`; exactly one member
has `owner=true` for a valid non-tie group.

`PerSeedMetric`:

```json
{
  "model_seed":653001,
  "validation_mae":0.0,
  "checkpoint":{"role":"string","path":"string","sha256":"sha256","size_bytes":0}
}
```

`EvalShardRecord`:

```json
{
  "arm":"stochastic",
  "shard_index":0,
  "seed_start":651001,
  "seed_end":651016,
  "seed_count":16,
  "terminal_run_count":16,
  "status":"passed|failed",
  "wall_clock_seconds":0.0
}
```

`CoverageRecord`:

```json
{
  "D":1,
  "L":1,
  "M":1,
  "F":0,
  "L_over_D":1.0,
  "F_over_M":0.0,
  "passed":true
}
```

All numeric metrics are finite. Arrays use the ordering frozen below.

### Common StageOutcome envelope

Every committed stage report has exactly these top-level keys:

```json
{
  "schema_id":"string",
  "schema_version":1,
  "task_id":"T075",
  "run_head":"sha256",
  "stage":"StageName",
  "valid":true,
  "passed":true,
  "parents":[ArtifactIdentity],
  "outputs":[ArtifactIdentity],
  "evidence":{},
  "problems":["string"]
}
```

Rules:

- valid successful pre-gate stage: `valid=true`, `passed=true`, `problems=[]`;
- invalid stage: `valid=false`, `passed=false`, `problems` non-empty;
- GATE/EVAL valid negative: `valid=true`, `passed=false`;
- report identity uses role `stage_outcome:<StageName>`;
- fixed report path is specified below.

## Stage Report Schemas

### PREFLIGHT — `t075-preflight-report-v1`

Path: `stage0-preflight.json`.

Parents: `[]`. Outputs: `[]`.

Evidence has exactly:

```json
{
  "recovery_base":"sha256",
  "t065_approved_spec_commit":"sha256",
  "sts_lightspeed_integration_commit":"sha256",
  "model_input_schema_id":"non-combat-model-input-v1",
  "state_dimension":4737,
  "action_dimension":92,
  "checks":[CheckRecord]
}
```

`checks` order and names are exactly:

1. `runtime_imports`
2. `simulator_identity`
3. `checkpoint_roundtrip`
4. `frozen_controller_action_space`
5. `model_input_schema_dimensions`
6. `public_input_firewall_capability`
7. `torch_runtime`

Any failed check makes PREFLIGHT invalid.

### SOURCE_REUSE — `t075-source-reuse-report-v1`

Path: `stage0-source-reuse.json`.

Parents, exact order:

1. PREFLIGHT report identity;
2. frozen stochastic source identity;
3. frozen expert source identity.

Outputs: `[]`.

Evidence has exactly:

```json
{"sources":[SourceRecord],"all_sources_valid":true}
```

Source order is stochastic then expert. `all_sources_valid=true` only when both
exact sources pass every frozen predicate.

### Ownership audit — `t075-ownership-audit-v1`

Path: `stage1-ownership-audit.json`. This is a data artifact, not a StageOutcome.

Top-level keys are exactly:

```text
schema_id
schema_version
task_id
run_head
parents
selection_strategy_id
replay_identity
 group_domain
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

With exact types:

```text
schema_id = "t075-ownership-audit-v1"
schema_version = 1
task_id = "T075"
run_head = sha256
parents = [ArtifactIdentity] exactly PREFLIGHT, SOURCE_REUSE
selection_strategy_id = "leakage-safe-global-owner-v1"
replay_identity = "(family,public_state_identity,ordered_legal_action_identities)"
group_domain = "T075-replay-group-v1"
candidate_domain_counts = [FamilySplitCount]
group_count = nonneg_int
singleton_group_count = nonneg_int
non_singleton_group_count = nonneg_int
cross_split_group_count = nonneg_int
excluded_non_owner_count = nonneg_int
group_counts_by_family = [{"family":Family,"count":nonneg_int}]
group_counts_by_split = [SplitCount]
group_size_histogram = [HistogramBin]
owner_counts_by_family_split = [FamilySplitCount]
groups = [OwnershipGroup]
problems = [string]
```

Ordering:

- family order: MAP_SCREEN, REST_ROOM, REWARDS, TREASURE_ROOM;
- split order: train, validation, heldout;
- family/split arrays use nested family then split order;
- histogram ascending `group_size`;
- groups ascending `group_digest`;
- members frozen `member_order_key` order.

### SELECTION_REPLAY — `t075-selection-report-v1`

Path: `stage1-selection-report.json`.

Parents, exact order: PREFLIGHT report, SOURCE_REUSE report.

Outputs, exact order:

1. `role=ownership_audit` identity;
2. `role=selected_states` identity for `stage1-selected-states.jsonl`.

Evidence has exactly:

```json
{
  "post_owner_available_counts":[FamilySplitCount],
  "selected_count":320,
  "selected_counts_by_family_split":[FamilySplitCount],
  "selected_replay_identity_digests":["sha256"],
  "replay":{
    "shard_count":16,
    "requested_worker_count":16,
    "actual_worker_count":16,
    "ranges":[RangeRecord],
    "attempted":320,
    "restored":320,
    "mismatch_count":0,
    "replacement_count":0,
    "duplicate_count":0,
    "cross_split_overlap_count":0,
    "wall_clock_seconds":0.0
  }
}
```

Family/split arrays use canonical nested order. `ranges` are shard index 0..15.
The digest list is selected-state index order 0..319.

Selected states are JSONL: exactly one strict current `t065-source-state-v1`
object per line, selected-state index order 0..319, final newline, no wrapper.

### TARGET scientific payload

Path: `stage2-target-table.json`.

Payload uses unchanged strict `t065-counterfactual-target-table-v1` version 1 and
existing T065 semantics. T075 does not add scientific payload fields.

### TARGET — `t075-target-validation-report-v1`

Path: `stage2-validation.json`.

Parents, exact order: PREFLIGHT report, SELECTION_REPLAY report, selected states.

Success outputs: exactly `role=target_table` identity. Invalid TARGET outputs:
`[]`.

Evidence has exactly:

```json
{
  "selected_state_count":320,
  "target_row_count":0,
  "eligible_action_count":0,
  "family_split_state_counts":[FamilySplitCount],
  "continuation_replication_counts_by_split":[SplitCount],
  "shard_count":16,
  "requested_worker_count":16,
  "actual_worker_count":16,
  "ranges":[RangeRecord],
  "checks":[CheckRecord],
  "violation_counts":{
    "missing_rows":0,
    "duplicate_rows":0,
    "nonfinite_targets":0,
    "model_input_mismatches":0,
    "lineage_mismatches":0,
    "legal_action_mismatches":0,
    "continuation_seed_mismatches":0,
    "firewall_violations":0
  },
  "stage3_barrier_passed":true,
  "wall_clock_seconds":0.0
}
```

`checks` is exactly the ten TARGET-barrier names in the order frozen above.
`ranges` are shard 0..15. On a completed barrier failure, evidence retains the
observed counts, `stage3_barrier_passed=false`, report is invalid, and outputs are
empty.

### TRAIN — `t075-training-report-v1`

Path: `stage4-training-report.json`.

Parents, exact order: TARGET validation report, target table.

Outputs: checkpoint identities ordered seed 653001 then 653002 with roles
`checkpoint:653001`, `checkpoint:653002`.

Evidence has exactly:

```json
{
  "model_seeds":[653001,653002],
  "training_config":{
    "device":"cpu",
    "huber_delta":1.0,
    "optimizer":"Adam",
    "learning_rate":0.001,
    "steps":1500,
    "minibatch_size":64,
    "sample_with_replacement":true,
    "gradient_clip":10.0,
    "torch_threads":1,
    "early_stopping":false
  },
  "normalizer":{
    "fit_split":"train",
    "dtype":"float32",
    "state_dimension":4737,
    "std_floor":1.0,
    "sha256":"sha256"
  },
  "per_seed_metrics":[PerSeedMetric],
  "selected_model_seed":653001,
  "selected_checkpoint":{"role":"string","path":"string","sha256":"sha256","size_bytes":0},
  "wall_clock_seconds":0.0
}
```

`per_seed_metrics` order is 653001, 653002. `selected_model_seed` is whichever
frozen MAE rule selects; the example value above is a type example, not a frozen
winner.

### GATE — `t075-stage5-report-v1`

Path: `stage5-heldout-report.json`.

Parents, exact order: TRAIN report, selected checkpoint, target table.

Outputs: `[]`.

Evidence has exactly:

```json
{
  "heldout_state_count":64,
  "selected_model_seed":653001,
  "non_selected_model_seed":653002,
  "mean_paired_delta":0.0,
  "median_paired_delta":0.0,
  "family_mean_deltas":[FamilyValue],
  "p_positive":0.0,
  "non_selected_mean_paired_delta":0.0,
  "violation_counts":{
    "hidden":0,
    "schema":0,
    "legal":0,
    "replay":0,
    "supported_screen_fallback":0
  },
  "gate_predicates":[PredicateRecord],
  "wall_clock_seconds":0.0
}
```

Family values use canonical family order. Gate predicate names/order are exactly:

1. `aggregate_mean_positive`
2. `median_nonnegative`
3. `three_of_four_family_means_nonnegative`
4. `bootstrap_p_positive_ge_0_90`
5. `non_selected_seed_mean_nonnegative`
6. `zero_violations`

A complete valid report may have `passed=false`, producing Case C.

### EVAL — `t075-stage6-report-v1`

Path: `stage6-complete-run-report.json`, present only after valid GATE pass.

Parents, exact order: GATE report, selected checkpoint.

Outputs: `[]`.

Evidence has exactly:

```json
{
  "fresh_seed_start":651001,
  "fresh_seed_end":651256,
  "arm_order":["stochastic","expert","learned"],
  "requested_run_count":768,
  "terminal_run_count":768,
  "shard_count_per_arm":16,
  "requested_worker_count":16,
  "actual_worker_count":16,
  "shards":[EvalShardRecord],
  "coverage":CoverageRecord,
  "mean_terminal_floor_delta":0.0,
  "p_positive":0.0,
  "learned_act2_entry_count":0,
  "expert_act2_entry_count":0,
  "controller_error_count":0,
  "truncation_count":0,
  "gate_predicates":[PredicateRecord],
  "wall_clock_seconds":0.0
}
```

Shards order: stochastic 0..15, expert 0..15, learned 0..15. Gate predicate
names/order are exactly:

1. `mean_terminal_floor_delta_positive`
2. `bootstrap_p_positive_ge_0_80`
3. `learned_act2_ge_expert`
4. `zero_controller_errors_and_truncations`
5. `coverage_pass`
6. `stronger_signal`

A complete valid report may have `passed=false`, producing Case B.

### Terminal decision — `t075-terminal-decision-report-v1`

Path: `terminal-decision-report.json`.

Top-level keys exactly:

```text
schema_id
schema_version
task_id
run_head
terminal_case
terminal_stage
reached_stages
skipped_stages
stage_report_identities
recommendation
problems
```

Types/rules:

```text
schema_id = "t075-terminal-decision-report-v1"
schema_version = 1
task_id = "T075"
run_head = sha256
terminal_case = A | B | C | D
terminal_stage = StageName
reached_stages = [StageName] canonical prefix through terminal_stage
skipped_stages = [StageName] remaining suffix
stage_report_identities = [ArtifactIdentity] canonical reached-stage order
recommendation = string
problems = [string]
```

For A/B terminal stage is EVAL; C is GATE; D is the first invalid stage. The
terminal report is derived only from canonical AcceptanceState and committed
ledger. `recommendation` contains exactly one planner-facing recommendation; for
D it is limited to repairing the same frozen experiment.

### Final retention — `t075-retention-manifest-v1`

Path: `t075-retention-manifest.json`.

Top-level keys exactly:

```text
schema_id
schema_version
task_id
run_head
terminal_case
retention_owner
retention_reason
terminal_report_identity
reused_artifacts
produced_artifacts
downstream_consumers
deletion_condition
problems
```

Types/rules:

```text
schema_id = "t075-retention-manifest-v1"
schema_version = 1
task_id = "T075"
run_head = sha256
terminal_case = A | B | C | D
retention_owner = "T075"
retention_reason = string
terminal_report_identity = ArtifactIdentity
reused_artifacts = [ArtifactIdentity]
produced_artifacts = [ArtifactIdentity]
downstream_consumers = [string]
deletion_condition = string
problems = [string]
```

`reused_artifacts` is stochastic source then expert source. `produced_artifacts`
contains every committed reached-stage report and durable data output in canonical
stage order, then role/path order within stage. There is no recursive lineage
rediscovery.

## Minimal Semantic Lineage

Required relationships are exactly:

| Output | Required semantic parents |
|---|---|
| SOURCE_REUSE report | PREFLIGHT + exact two frozen T065 sources |
| ownership audit | PREFLIGHT + SOURCE_REUSE |
| selected states / SELECTION_REPLAY report | PREFLIGHT + SOURCE_REUSE + ownership audit |
| TARGET table / validation | PREFLIGHT + SELECTION_REPLAY + selected states |
| TRAIN report/checkpoints | valid committed TARGET + target table |
| GATE report | TRAIN + selected checkpoint + target table |
| EVAL report | valid GATE pass + selected checkpoint + frozen fresh seed set |
| terminal report | canonical AcceptanceState + committed stage reports |
| final retention manifest | terminal report + committed reached-stage artifacts |

Parent comparison uses exact `ArtifactIdentity`. There is no per-stage retention
manifest, recursive proof graph, historical alias resolver, exact command-token
identity, or task-specific PID proof.

## Frozen Durable Output Surface

Under `artifacts/t075-leakage-safe-non-combat-cohort-repair/`:

```text
stage0-preflight.json
stage0-source-reuse.json
stage1-ownership-audit.json
stage1-selected-states.jsonl
stage1-selection-report.json
stage2-target-table.json
stage2-validation.json
stage4-checkpoints/
stage4-training-report.json
stage5-heldout-report.json
stage6-complete-run-report.json        # only if EVAL reached
terminal-decision-report.json
t075-retention-manifest.json
```

Temporary data is not canonical and lives under `ROOT/.tmp/` or an equivalent
explicitly uncommitted subpath.

## Retention Ownership And Deletion Conditions

T075 owns produced durable outputs from the first committed StageOutcome until the
terminal result is merged or the recovery line is formally abandoned.

T075 places a consumer hold on the two T065 raw sources. It never deletes or
rewrites them. The T075 hold is released only after:

1. terminal T075 result and final retention manifest are merged, or Planner
   formally closes T075 without scientific execution;
2. no open/approved task names the sources as required inputs;
3. no Maintainer reproduction hold remains.

T075-produced large payloads/checkpoints may be deleted only after:

1. terminal T075 result is merged;
2. final retention manifest and compact reached-stage reports are retained;
3. no open/approved downstream task consumes the payload;
4. no reproduction hold remains.

Deletion never changes recorded historical identities.

## Frozen Shard And Worker Plan

The authoritative run uses the repository's 16-logical-core Maintainer resource
assumption.

### SELECTION_REPLAY and TARGET

Exactly 16 contiguous 20-state shards. For shard `i=0..15`:

```text
start = 20*i
end = 20*i + 19
count = 20
```

Requested and required actual worker count: 16.

### EVAL

For each arm, exactly 16 contiguous 16-seed shards over `651001..651256`. For
shard `i=0..15`:

```text
start = 651001 + 16*i
end = 651016 + 16*i
count = 16
```

Arm order: stochastic, expert, learned. Requested and required actual worker count
per active arm batch: 16; at most 16 concurrent simulator workers.

If the host cannot establish the required worker plan before a substantial stage,
the stage does not start and no StageOutcome is committed. This is operationally
incomplete, not Case D. The Maintainer resolves the resource constraint or returns
a resource/contract gap; implementation must not silently downgrade authoritative
execution.

Each substantial stage records exact shard ranges, requested/actual workers,
completion counts, and wall-clock seconds. PID, queue mechanics, and process
binding are non-semantic.

## Exact Reproduction Commands

The implementation extends the neutral
`sts_combat_rl.commands.non_combat_learning` module. It does not add T075 routes to
the legacy flat CLI and does not create a task-numbered production package.

Semantic arguments, inputs, outputs, and executable paths below are normative.
Shell quoting, literal token sequence, launcher formatting, and command-text hash
are not scientific evidence and must not be validated by string equality.

Common setup:

```bash
CODE=/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-architecture-recovery
BRANCH=task/T075-architecture-recovery
PY=/home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
STABLE=/mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT=$STABLE/t075-leakage-safe-non-combat-cohort-repair
T065=$STABLE/t065-learned-non-combat-policy-v1
cd "$CODE"
export PYTHONPATH="$NATIVE:$CODE/src"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$RUN_HEAD"
```

### Local and acceptance gates

All Python-owned gates use the same pinned `$PY`; unqualified `python`, `pytest`,
and `ruff` are not part of the T075 reproduction contract.

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

If the pinned `$PY` lacks a required development module, execution readiness is
not satisfied; do not silently substitute another interpreter.

### PREFLIGHT

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

### SOURCE_REUSE

```bash
$PY -m sts_combat_rl.commands.non_combat_learning validate-reuse \
  --source "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --source "$T065/source-expert-650001-650256-deeaa46.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --output "$ROOT/stage0-source-reuse.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

There is no T075 `collect` invocation.

### SELECTION_REPLAY

```bash
$PY -m sts_combat_rl.commands.non_combat_learning select \
  --input "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --input "$T065/source-expert-650001-650256-deeaa46.json" \
  --source-reuse "$ROOT/stage0-source-reuse.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --output "$ROOT/stage1-selected-states.jsonl" \
  --ownership-audit "$ROOT/stage1-ownership-audit.json" \
  --selection-report "$ROOT/stage1-selection-report.json" \
  --selection-strategy leakage-safe-global-owner-v1 \
  --replay-shard-count 16 --replay-worker-count 16 \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

### TARGET + logical Stage 3

```bash
$PY -m sts_combat_rl.commands.non_combat_learning target \
  --states "$ROOT/stage1-selected-states.jsonl" \
  --selection-report "$ROOT/stage1-selection-report.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --output "$ROOT/stage2-target-table.json" \
  --validation-report "$ROOT/stage2-validation.json" \
  --shard-count 16 --worker-count 16 \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

### TRAIN

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --target-validation "$ROOT/stage2-validation.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

### GATE

```bash
$PY -m sts_combat_rl.commands.non_combat_learning gate \
  --target-table "$ROOT/stage2-target-table.json" \
  --training-report "$ROOT/stage4-training-report.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

A valid GATE failure atomically commits Case C and EVAL does not run.

### EVAL

```bash
$PY -m sts_combat_rl.commands.non_combat_learning eval \
  --stage5-report "$ROOT/stage5-heldout-report.json" \
  --training-report "$ROOT/stage4-training-report.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage6-complete-run-report.json" \
  --shard-count 16 --worker-count 16 \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

### Finalization

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --terminal-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json" \
  --run-head "$RUN_HEAD"
```

`finalize` validates and retains existing canonical terminal state. It never
recomputes A/B/C/D.

## Allowed Implementation Freedom

The Implementer may choose:

- exact Python class/function names for the frozen types;
- atomic-write helper details;
- process-pool/queue implementation;
- temporary file naming under the uncommitted area;
- non-normative logs outside the frozen artifacts;
- reuse of small generic execution helpers already on `main`.

The command layer must remain thin: parse frozen stage arguments, load strict
parents, invoke one stage adapter, use canonical transition authority, and persist
artifacts. It must not become a second workflow engine.

## Explicitly Forbidden Recovery Work

Do not:

- cherry-pick or mechanically port rejected PR #75 orchestration;
- preserve its large task-specific `_t075_*` lifecycle-validator cluster;
- derive acceptance expected values from production helpers under test;
- add per-stage retention manifests;
- recursively search lineage to rediscover exact inputs;
- search historical aliases for frozen sources;
- require exact command-string/token equality as scientific evidence;
- treat worker PID/process-binding details as scientific acceptance;
- add acceptance-relevant schema fields outside this contract without Planner
  revision;
- create a generic workflow framework or task-numbered production package;
- change T075 science to simplify implementation;
- recollect Stage-1 sources;
- reuse PR #75 runtime outputs as authoritative recovery evidence;
- run Stage 0--6 before implementation, A01--A24, and exact `RUN_HEAD` are frozen.

## Selective Salvage Boundary

Safe to consider for salvage:

1. global-ownership scientific primitive and canonical ordering helpers;
2. merged T065 strict readers, model-input, target, training, evaluation
   primitives;
3. implementation-independent fixtures encoding literal frozen facts;
4. generic spawn/process primitive only if it contains no T075 acceptance,
   artifact, terminal, or command semantics.

Default rewrite boundary:

- T075 command/orchestration layer;
- T075 terminal/finalization validators;
- T075 command matching;
- T075 path/retention traversal specific to PR #75;
- T075 partial-process/PID evidence machinery;
- acceptance tests coupled to private production helpers.

Anything outside the safe list requires Maintainer proof that it implements an
already-frozen contract row; otherwise report `ARCHITECTURE_ESCALATION`.

## Normative Acceptance Matrix

Before production implementation, the Maintainer translates A01--A24 into an
implementation-independent executable test-only boundary. Expected literals and
fixtures must not be generated by production code under test.

| ID | Scenario | Required result |
|---|---|---|
| A01 | exact frozen source files and metadata | SOURCE_REUSE pass |
| A02 | missing/hash-invalid/metadata-invalid frozen source | D at SOURCE_REUSE |
| A03 | cross-split replay-equivalent raw candidates | deterministic global owner; not itself an error |
| A04 | exact full member-order tie between distinct rows | D at SELECTION_REPLAY |
| A05 | owner bucket below 48/16/16 quota | D at SELECTION_REPLAY |
| A06 | selected duplicate/cross-split replay overlap | D at SELECTION_REPLAY |
| A07 | all 320 selected states replay exactly under 16x20/16-worker plan | SELECTION_REPLAY pass |
| A08 | one selected replay mismatch | D; no replacement |
| A09 | TARGET missing/duplicate/nonfinite/wrong action order/continuation seed | committed invalid TARGET; D at TARGET |
| A10 | TARGET public-input firewall or semantic lineage failure | committed invalid TARGET; D; TRAIN forbidden |
| A11 | target work exists but StageOutcome commit absent due interruption | TARGET uncommitted; no terminal; retry allowed |
| A12 | valid committed TARGET + valid training | GATE reached |
| A13 | valid Stage-5 pass | EVAL reached |
| A14 | valid Stage-5 fail | terminal C at GATE; EVAL absent |
| A15 | invalid Stage-5 evidence | terminal D at GATE |
| A16 | valid Stage-6 pass | terminal A at EVAL |
| A17 | valid Stage-6 fail | terminal B at EVAL |
| A18 | invalid/missing/truncated/controller-invalid Stage-6 evidence | terminal D at EVAL |
| A19 | initial state | empty ledger; current PREFLIGHT; terminal_case/stage null |
| A20 | wrong RUN_HEAD, out-of-order, or conflicting duplicate | reject operationally; ledger/state/terminal unchanged |
| A21 | interruption before any StageOutcome atomic commit | no scientific terminal; same stage retryable |
| A22 | exact committed StageOutcome retry, including after current stage advanced or terminal committed | duplicate check precedes current-stage/terminal rejection; identity match is idempotent and science does not rerun |
| A23 | deployable public input contains behavior/expert/target/hidden/future field | committed invalid TARGET; D at TARGET |
| A24 | command/helper/finalizer disagrees with canonical `advance`, terminal report conflicts with ledger, or final retention fails after terminal | disagreement/conflict is IMPLEMENTATION_BUG or operational integrity failure; retention failure is operational; terminal unchanged |

A focused implementation regression may be added without changing semantics. A
new semantic scenario or outcome not unambiguously covered above is a
`CONTRACT_GAP`; production changes stop and return to Planner.

## Verification Sequence

1. Planner contract only; no production code.
2. Maintainer execution-readiness review of exact contract.
3. Test-only executable A01--A24 boundary.
4. Baseline A01--A24 against clean pre-implementation `main` where meaningful.
5. Maintainer publishes exact-head `SPEC APPROVED` /
   `implementation_authorized=true`.
6. One bounded production implementation pass.
7. Run A01--A24, focused tests, full tests, compile/lint/format/mock gates.
8. Maintainer reviews full matrix and architecture as one unit.
9. Freeze exact implementation `RUN_HEAD`.
10. Run authoritative T075 stages from that clean head only.
11. Materialize exactly one terminal A/B/C/D and final retention manifest.
12. Planner exact-head scientific/architecture acceptance.
13. Maintainer exact-head implementation/operational acceptance and merge.

No scientific Stage 0--6 execution begins before step 9.

## Review Finding Classification

After implementation starts:

- contract defines correct behavior and code violates it: `IMPLEMENTATION_BUG`;
- correct behavior is not unambiguously defined: `CONTRACT_GAP`; stop and return
  to Planner;
- successive passes reveal a new cross-module semantic class, duplicated lifecycle
  logic, growing validator glue, or loss of one canonical authority:
  `ARCHITECTURE_ESCALATION`; stop incremental patching.

A corrective pass followed by another newly identified cross-module semantic
class is presumed architecture escalation unless the Maintainer can point to an
existing acceptance row that already defines both behaviors.

## Required PR Evidence

The recovery PR must report:

- exact approved contract commit and implementation `RUN_HEAD`;
- proof PR #75 orchestration/runtime artifacts were not authoritative recovery
  state;
- T065 approved-spec and `sts_lightspeed` integration identities;
- retained source identities and strict validation result;
- raw candidate/group/owner counts and post-owner family/split availability;
- selected 320-state counts and replay result;
- all reached target/training/gate/evaluation metrics;
- shard/worker/range and wall-clock evidence for substantial stages;
- exact terminal A/B/C/D and terminal stage;
- final artifact identities in `t075-retention-manifest.json`;
- any `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION`;
- one next scientific recommendation only after a valid terminal result.

## Final Planner Review Checklist

The Planner will not provide scientific/architectural acceptance unless the exact
final head satisfies all of the following:

- T075 remains only the global-ownership cohort-partition repair scientifically;
- one canonical acceptance transition authority exists in production;
- AcceptanceState contains the committed-outcome ledger and terminal stage;
- duplicate identity is checked before current-stage/terminal rejection;
- invalid TARGET barrier failures atomically commit invalid StageOutcome while
  interruptions remain retryable and non-terminal;
- terminal A/B/C/D semantics are not duplicated across CLI, validators, and
  finalization helpers;
- B/C remain valid negative science and D remains invalid experiment;
- artifact serialization implements the shared exact types and stage evidence
  schemas above, without process-manager ceremony;
- lineage is explicit and minimal rather than recursive proof machinery;
- one exact `RUN_HEAD` owns authoritative scientific execution;
- acceptance expected values are implementation independent;
- pinned `$PY` owns Python/test/lint/format/mock gates;
- command code remains thin and does not become a hidden workflow engine;
- frozen 16-shard/16-worker operational protocol is followed and reported;
- PID/queue/process-binding details are not scientific semantics;
- no hidden/human-policy information enters the deployable model;
- no frozen T065 scientific constant changed;
- no authoritative runtime artifact from rejected PR #75 is reused;
- no unreviewed semantic case is patched locally.

## Lifecycle

This recovery contract remains `DRAFT` until the Main Maintainer performs
execution-readiness review and posts exact-head `SPEC APPROVED` /
`implementation_authorized=true`.

That approval authorizes only bounded implementation against this contract. It
does not authorize the Maintainer or Implementer to redesign T075 semantics.

PR #75 remains the linked unmerged audit record of the rejected architecture.
