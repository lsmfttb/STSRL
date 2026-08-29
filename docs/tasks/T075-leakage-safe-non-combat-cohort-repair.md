# T075: Leakage-Safe Non-Combat Cohort Repair

## Architecture Recovery Declaration

This document is the single normative Planner contract for the T075 recovery line.
It supersedes the unmerged T075 specification/implementation history on PR #75 for
all future implementation and acceptance decisions.

PR #75 is retained only as an architecture-failure audit record. Its production
implementation, task-specific orchestration, validators, exact-command matching,
per-stage retention machinery, acceptance helpers, and runtime artifacts are not
accepted project state and must not be used as the recovery implementation
baseline.

The accepted scientific primitive from that line is the leakage-safe global
ownership rule described below. Implementation-independent acceptance ideas and
truly generic execution primitives may be selectively salvaged only when this
contract explicitly allows them.

Architecture recovery base:

`bc9a6790f36ff036f90dc7f03ba0ff026a16788d`

Historical references:

- accepted T065 result: merged task T065;
- rejected T075 implementation/audit line: PR #75;
- previously approved T075 proposal: `e204c5d28cc0bee8013853e8680e8966f5c930a8`.

The recovery keeps the T075 scientific experiment and replaces the rejected
control-plane architecture with one canonical acceptance model, transactional
stage commits, minimal semantic artifact lineage, and one frozen scientific
`RUN_HEAD`.

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
- T065 learned non-combat workflow, readers, retained Stage-1 evidence, and valid
  Case-D result;
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
integration is not an implementer-chosen compatibility rule. Before scientific
execution it blocks readiness; if detected by the frozen T075 PREFLIGHT under the
correct `RUN_HEAD`, it produces invalid PREFLIGHT evidence and Case D.

T034, T063, and T066 remain outside T075.

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

The authoritative recovery implementation and scientific execution use exactly:

```text
BRANCH = task/T075-architecture-recovery
CODE = /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/t075-architecture-recovery
PY = /home/lsmft/stsrl-spikes/py313-torch/bin/python
NATIVE = /home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch
STABLE = /mnt/d/DeadlycatCoding/STSRL/artifacts
ROOT = ${STABLE}/t075-leakage-safe-non-combat-cohort-repair
T065 = ${STABLE}/t065-learned-non-combat-policy-v1
```

All task commands run from `CODE` with:

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

A wrong branch, dirty checkout, missing `RUN_HEAD`, or `HEAD != RUN_HEAD` rejects
the command before scientific stage execution. It is an operational invocation
failure: no `StageOutcome` is committed and no Case A/B/C/D is created.

If production code changes after authoritative scientific execution starts, the
old `RUN_HEAD` is retired. The Maintainer identifies the earliest semantically
affected stage, freezes a new `RUN_HEAD` only after acceptance tests pass again,
and reruns the affected stage and all downstream stages. PR #75 runtime outputs
are never eligible authoritative recovery evidence.

## Frozen T065 Scientific Inputs

### Retained Stage-1 source evidence

T075 reuses exactly these two retained T065 raw source files and never recollects
them:

| Arm | Relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

The files must pass the current strict T065 source reader and match all of the
following frozen metadata:

- schema `t065-learned-non-combat-policy-v1`, version `1`;
- `approved_spec_commit == T065_APPROVED_SPEC`;
- exact current `T065ExperimentConfig().to_dict()`;
- expected source arm;
- source driver seed `654001`;
- source seeds exactly `650001..650256`;
- requested/terminal run count `256`;
- truncated run count `0`;
- failed run count `0`;
- original topology 16 ordered shards x 16 seeds and effective worker count 16;
- frozen action space;
- battle provenance `oracle_search_v1_highest_mean_s20`;
- simulator identity backed by `STS_LIGHTSPEED_INTEGRATION`;
- no source-level problems.

The exact file identities above are sufficient T075 input identity. T075 must not
rediscover these sources through retention manifests, historical aliases,
basename search, or recursive provenance traversal.

If either exact file is missing, unreadable, hash/size invalid, or fails strict
metadata validation, `SOURCE_REUSE` is invalid and T075 ends Case D.

Source recollection, source replacement, alternate aliases, and best-effort input
discovery are forbidden.

### Source and split constants

- player: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- source seeds: `650001..650256`;
- source driver seed: `654001`;
- source arms: `stochastic_non_combat_v1`, `expert_non_combat_v1`;
- battle controller provenance: `oracle_search_v1_highest_mean_s20`;
- original source topology: 16 shards per arm, 16 seeds per shard.

Seed-derived splits remain:

- train: `650001..650154`;
- validation: `650155..650205`;
- heldout: `650206..650256`.

No simulator seed may change split.

### Mandatory families and quotas

Canonical family order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas:

- train: 48;
- validation: 16;
- heldout: 16.

A valid cohort has exactly 320 selected states. Other screens remain fallback-only
and are not selectable training states.

### Public model input

Use `non-combat-model-input-v1` exactly:

- tactical snapshot dimension: 4634;
- public context dimension: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- no expert/behavior/target/outcome/hidden/future feature;
- training-split-only CPU float32 population normalization;
- population std is clamped to at least 1.0 and checkpointed unchanged for later
  stages.

## T075 Scientific Primitive: Global Ownership

Selectable candidates must:

- pass the strict `t065-source-state-v1` reader;
- come from a problem-free terminal source run;
- belong to a mandatory family;
- retain the split implied by their simulator seed;
- retain source provenance;
- pass existing T065 public/model/action/replay validation.

Malformed or provenance-invalid rows fail closed. Nonterminal or truncated rows
remain source evidence but are not selectable.

Replay equivalence remains exactly:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical member order remains T065:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Replay-group audit identity is:

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

Canonical JSON for scientific digest material uses UTF-8, sorted keys, compact
separators `(',', ':')`, `ensure_ascii=False`, and `allow_nan=False`.

Ownership algorithm:

1. admit all selectable candidates from both source arms and every frozen split;
2. group globally by the unchanged replay-equivalence key;
3. sort each group by `member_order_key`;
4. if two distinct source rows have an identical complete `member_order_key`,
   fail Case D at `SELECTION_REPLAY`; do not invent another tie breaker;
5. otherwise the first member is the sole owner;
6. exclude all non-owners before quota selection;
7. keep the owner's seed-derived split;
8. inside each `(family, split)` owner bucket, sort by the same member order and
   take exactly the frozen 48/16/16 quota.

If any owner bucket is below quota, T075 ends Case D. There is no recollection,
scale increase, split reassignment, balancing, target-aware selection, strategic
quality filter, manual replacement, or replay-key change.

A valid selected cohort has:

- exactly 320 states;
- exact 48/16/16 per family;
- globally unique replay-equivalence keys;
- zero selected cross-split replay overlap;
- zero simulator-seed split leakage;
- exact replay of every selected public/model state and ordered legal actions;
- zero replacement after replay failure.

## Unchanged Downstream Science

### Counterfactual targets

Every selected state evaluates every eligible legal action from the same restored
checkpoint.

Continuation controller: `expert_non_combat_v1`.

Continuation seeds:

- train: `(652001, 652002)`;
- validation: `(652101, 652102)`;
- heldout: `(652201, 652202, 652203, 652204)`.

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

Use the 64 held-out states. A valid Stage-5 report passes only if all are true:

1. aggregate mean paired `q_floor(model)-q_floor(expert) > 0`;
2. median paired delta `>= 0`;
3. at least 3 of 4 family mean deltas `>= 0`;
4. 10,000-stratified-bootstrap `p_positive >= 0.90` using
   `random.Random(655001)`;
5. the non-selected model seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violation.

A valid Stage-5 failure is Case C and Stage 6 is skipped.

### Conditional Stage-6 complete-run gate

Run only after a valid Stage-5 pass.

- fresh seeds: `651001..651256`;
- driver/fallback seed: `654002`;
- matched arm order: stochastic, expert, learned-on-mandatory-families with
  expert fallback elsewhere;
- 16 fixed shards x 16 seeds per arm;
- 768 valid terminal runs required;
- bootstrap: 10,000 matched-seed resamples using `random.Random(655002)`;
- coverage: `L/D >= 0.60`, `F/M <= 0.01`, `D != 0`, `M != 0`, with unchanged
  T065 D/L/M/F definitions.

A valid Stage-6 report passes only if:

1. matched mean terminal-floor delta `> 0`;
2. bootstrap `p_positive >= 0.80`;
3. learned Act-2 entry count `>=` expert;
4. zero controller errors and unreported truncations;
5. coverage passes;
6. at least one stronger signal holds: learned Act-2 count `>` expert or
   `p_positive >= 0.95`.

## Canonical Acceptance Model

T075 has exactly one production-side acceptance authority. CLI handlers, artifact
readers, validators, persistence code, and finalization code must not implement
independent transition logic.

The implementation may choose exact Python names, but must be structurally
equivalent to:

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
  repository-relative POSIX path
  sha256
  size_bytes

StageOutcome =
  stage
  run_head
  valid: bool
  passed: bool
  parents
  outputs
  evidence
  problems

AcceptanceState =
  run_head
  completed_stages
  current_stage
  terminal_case or none
```

There must be one pure or effectively pure transition authority equivalent to:

```text
advance(AcceptanceState, StageOutcome) -> AcceptanceState
```

### Initial state

After `RUN_HEAD` is frozen and before any StageOutcome exists:

```text
run_head = RUN_HEAD
completed_stages = ()
current_stage = PREFLIGHT
terminal_case = None
```

The durable state is reconstructed by replaying committed StageOutcome reports in
canonical stage order through `advance`. A separate mutable workflow-state file is
not required and must not become a second transition authority.

### Legal scientific transitions

```text
PREFLIGHT valid+pass        -> SOURCE_REUSE
PREFLIGHT invalid           -> D

SOURCE_REUSE valid+pass     -> SELECTION_REPLAY
SOURCE_REUSE invalid        -> D

SELECTION_REPLAY valid+pass -> TARGET
SELECTION_REPLAY invalid    -> D

TARGET valid+pass           -> TRAIN
TARGET invalid              -> D

TRAIN valid+pass            -> GATE
TRAIN invalid               -> D

GATE valid+pass             -> EVAL
GATE valid+fail             -> C
GATE invalid                -> D

EVAL valid+pass             -> A
EVAL valid+fail             -> B
EVAL invalid                -> D
```

For PREFLIGHT, SOURCE_REUSE, SELECTION_REPLAY, TARGET, and TRAIN,
`valid=true, passed=false` is illegal and must not be emitted.

Meaning of terminal cases:

```text
A = valid positive Stage-6 transfer result
B = valid Stage-6 negative result
C = valid Stage-5 negative result
D = invalid experiment / frozen-fidelity failure
```

Poor model performance alone can produce B or C, never D.

### Edge and illegal-state semantics

The following rules are part of the canonical model and are not CLI-specific
special cases.

1. **Out-of-order stage.** An outcome whose `stage != state.current_stage` is
   rejected as an illegal transition. State is unchanged; no scientific terminal
   case is produced.
2. **Wrong `RUN_HEAD`.** An outcome whose `run_head != state.run_head` is rejected.
   State is unchanged; no scientific terminal case is produced.
3. **Duplicate committed stage.** A command seeing an already committed valid
   outcome for the same stage and `RUN_HEAD` must not rerun science. It may return
   the existing committed outcome/state idempotently. A conflicting duplicate is
   an operational integrity failure and state remains unchanged.
4. **Incomplete retry.** If execution stops before a StageOutcome commit marker is
   atomically written, the stage is uncommitted and may be rerun from the same
   committed parents and `RUN_HEAD` with identical scientific settings.
5. **Committed semantic failure.** Once an invalid StageOutcome is committed, it
   is scientific/fidelity evidence and canonical `advance` yields Case D. The
   failed stage is not rerun to seek a better result.
6. **Parent mismatch.** A legitimately reached stage whose canonical committed
   parent artifact no longer matches its recorded `ArtifactIdentity`, or whose
   scientific lineage fails the stage validator, commits an invalid outcome and
   therefore D at that stage. Merely invoking a command with a wrong arbitrary
   path is an invocation error and does not create a StageOutcome.
7. **Terminal immutability.** After a valid terminal A/B/C/D is committed, no
   later stage or finalizer may change it.
8. **Missing terminal file after terminal StageOutcome.** If a committed stage
   outcome deterministically implies A/B/C/D but the terminal report was not
   written because of interruption, restart may materialize exactly that terminal
   report by replaying canonical `advance`; scientific computation is not rerun.
9. **Conflicting terminal report.** A terminal report inconsistent with the
   committed StageOutcome prefix is an operational integrity failure. Do not
   reinterpret the experiment or overwrite it with a different case.
10. **Finalization failure.** A failure while writing or validating final
    retention after a valid terminal commit is operational failure; the terminal
    case remains unchanged.

### First-valid terminal commit

`ROOT/terminal-decision-report.json` is the single terminal-decision path.
The first valid terminal case generated by the canonical transition authority is
immutable. Later commands may read or validate it, but may not infer another case.

## TARGET Transaction Barrier (Logical Stage 3)

Logical Stage 3 is a mandatory commit barrier inside `TARGET`; it is not a
separate execution stage.

Target generation is not `TARGET valid+pass` until the persisted target table is
reopened and all checks pass in this exact order:

1. `strict_target_reader`;
2. `target_completeness`;
3. `selected_state_lineage`;
4. `simulator_and_preflight_lineage`;
5. `model_input_schema`;
6. `state_action_dimensions`;
7. `finite_numeric_values`;
8. `legal_action_order`;
9. `continuation_seed_contract`;
10. `public_input_firewall`.

The validation report is the TARGET StageOutcome commit marker and must be
persisted only after validation has determined `valid`/`passed`.

If the barrier fails:

- T075 ends Case D at `TARGET`;
- diagnostic target/intermediate files may remain as uncommitted failure evidence;
- they are not valid parents for TRAIN;
- no successful TARGET outcome is committed.

## Transactional Stage Execution And Restart

Each stage uses this transaction shape:

1. validate current canonical state, `RUN_HEAD`, branch, clean checkout, and
   required committed parents;
2. write expensive/intermediate data to temporary paths under `ROOT/.tmp/` or an
   equivalent non-committed location;
3. run stage-specific completeness/fidelity validation;
4. move durable data outputs to their frozen paths;
5. compute their `ArtifactIdentity` values;
6. atomically write the stage's StageOutcome report last.

The StageOutcome report is the commit marker. Durable-looking data files without
the corresponding committed StageOutcome are uncommitted and must be ignored,
cleaned, or deterministically overwritten on retry.

A process interruption before step 6 is operationally incomplete and creates no
scientific terminal result. Do not build T075-specific machinery to preserve every
partial worker return, PID, queue message, or temporary file as scientific
evidence.

## Artifact Identity And Serialization

### Physical identity

Persistent artifact identity is exactly:

```text
(role, normalized_path, sha256, size_bytes)
```

`normalized_path` is repository-relative POSIX under `artifacts/`. Normalize
backslashes to `/`, remove `.` components and one leading `./`, reject `..`, and
compare case-sensitively. Basename-only matching is forbidden.

Content identities such as replay-group digest are separate from physical file
identity.

### Canonical T075 report serialization

All T075 JSON report/control artifacts use UTF-8 canonical JSON with:

```text
sort_keys=True
separators=(',', ':')
ensure_ascii=False
allow_nan=False
one trailing newline
```

JSON object insertion order is therefore not semantic. Array order is semantic
where frozen below.

The selected-state file remains JSONL: exactly one complete current
`t065-source-state-v1` object per line, selected-state indices `0..319`, final
newline, no wrapper object.

Existing unchanged T065 scientific payload schemas may keep their existing strict
writer/reader serialization. Their actual persisted bytes define their
`ArtifactIdentity`; T075 task provenance and lineage are carried by the T075
StageOutcome reports.

## Normative Artifact Schemas

### Common StageOutcome envelope

Every committed stage report has schema version `1` and these required fields:

```text
schema_id
schema_version
task_id = T075
run_head
stage
valid
passed
parents
outputs
evidence
problems
```

`parents` and `outputs` are arrays of complete `ArtifactIdentity` objects.
`problems` is an array of strings. `evidence` is an object whose required semantic
fields are defined per stage below.

For valid successful pre-gate stages: `valid=true`, `passed=true`, `problems=[]`.
For invalid stages: `valid=false`, `passed=false`, `problems` is non-empty.
For GATE/EVAL valid negative results: `valid=true`, `passed=false`; those are C/B,
not D.

### PREFLIGHT — `t075-preflight-report-v1`

Path: `stage0-preflight.json`.

Parents: `[]`.

Outputs: `[]`.

Required `evidence`:

```text
recovery_base
T065_approved_spec_commit
sts_lightspeed_integration_commit
simulator_identity
model_input_schema
checks
```

`checks` is an ordered list with exactly these names:

1. `runtime_imports`;
2. `simulator_identity`;
3. `checkpoint_roundtrip`;
4. `frozen_controller_action_space`;
5. `model_input_schema_dimensions`;
6. `public_input_firewall_capability`;
7. `torch_runtime`.

Each check records `status=passed|failed` and deterministic evidence/counts
needed to explain a failure. Any failed required check makes PREFLIGHT invalid.

### SOURCE_REUSE — `t075-source-reuse-report-v1`

Path: `stage0-source-reuse.json`.

Parents, exact order:

1. PREFLIGHT report identity;
2. frozen stochastic T065 source identity;
3. frozen expert T065 source identity.

Outputs: `[]`.

Required `evidence`:

```text
sources
validation
```

`sources` order is stochastic then expert. Each source entry requires `arm`,
`ArtifactIdentity`, strict schema/config/provenance validation status, seed range,
run counts, shard count, worker count, action-space identity, controller
provenance, and simulator identity. `validation` records whether all frozen
predicates passed.

### Ownership audit — `t075-ownership-audit-v1`

Path: `stage1-ownership-audit.json`.

This is a SELECTION_REPLAY data artifact, not a second StageOutcome.

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
run_head
parents
selection_strategy_id = leakage-safe-global-owner-v1
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

Parents, exact order: PREFLIGHT report, SOURCE_REUSE report.

Ordering:

- arm order: stochastic, expert;
- family order: MAP, REST, REWARDS, TREASURE;
- split order: train, validation, heldout;
- histogram ascending numeric group size;
- `groups` ascending `group_digest`;
- group members ascending complete `member_order_key`.

### SELECTION_REPLAY — `t075-selection-report-v1`

Path: `stage1-selection-report.json`.

Parents, exact order: PREFLIGHT report, SOURCE_REUSE report.

Outputs, exact order:

1. ownership audit identity;
2. selected-state JSONL identity.

Required `evidence`:

```text
post_owner_available_counts
selected_count
selected_counts_by_family_split
selected_replay_identity_digests
replay
```

`selected_count == 320`. Family/split ordering is canonical. `replay` requires:

```text
shard_count = 16
requested_worker_count = 16
actual_worker_count = 16
ranges = exact 000..019 ... 300..319 partition
attempted = 320
restored = 320
mismatch_count = 0
replacement_count = 0
duplicate_count = 0
cross_split_overlap_count = 0
wall_clock_seconds
```

Shard/range rows are ordered by shard index `0..15`. PID/process identity is not
part of this schema.

### TARGET scientific payload

Path: `stage2-target-table.json`.

The payload uses the unchanged strict T065 scientific target-table contract
`t065-counterfactual-target-table-v1` version `1` and existing T065 target
semantics. T075 does not add model features or target fields to that scientific
payload. Its physical identity and T075 lineage are committed by the TARGET
validation report below.

### TARGET — `t075-target-validation-report-v1`

Path: `stage2-validation.json`.

Parents, exact order:

1. PREFLIGHT report;
2. SELECTION_REPLAY report;
3. selected-state JSONL.

Outputs: target-table identity.

Required `evidence`:

```text
selected_state_count = 320
target_row_count
eligible_action_count
family_split_state_counts
continuation_replication_counts_by_split
shard_count = 16
requested_worker_count = 16
actual_worker_count = 16
ranges
checks
violation_counts
stage3_barrier_passed
wall_clock_seconds
```

`checks` is the exact ten-item TARGET barrier list in the order frozen above.
Each check records `passed|failed` plus deterministic counts. `violation_counts`
requires at least missing rows, duplicate rows, nonfinite targets, model-input
mismatches, lineage mismatches, legal-action mismatches, continuation-seed
mismatches, and firewall violations.

### TRAIN — `t075-training-report-v1`

Path: `stage4-training-report.json`.

Parents, exact order: TARGET validation report, target table.

Outputs: checkpoint file identities ordered by model seed `653001`, `653002`.
The checkpoint payloads retain the unchanged T065 checkpoint schema
`t065-non-combat-ranker-checkpoint-v1`.

Required `evidence`:

```text
model_seeds
training_config
normalizer_provenance
per_seed_metrics
selected_model_seed
selected_checkpoint_identity
wall_clock_seconds
```

Both model seeds must complete validly. The selected seed is determined only by
frozen validation MAE with lower-seed exact tie break.

### GATE — `t075-stage5-report-v1`

Path: `stage5-heldout-report.json`.

Parents, exact order: TRAIN report, selected checkpoint, TARGET table.

Outputs: `[]`.

Required `evidence`:

```text
heldout_state_count = 64
selected_model_seed
non_selected_model_seed
mean_paired_delta
median_paired_delta
family_mean_deltas
p_positive
non_selected_mean_paired_delta
violation_counts
gate_predicates
wall_clock_seconds
```

Family metrics use canonical family order. A complete valid report may have
`passed=false`, producing Case C.

### EVAL — `t075-stage6-report-v1`

Path: `stage6-complete-run-report.json` and exists only if GATE validly passes.

Parents, exact order: GATE report, selected checkpoint.

Outputs: `[]`.

Required `evidence`:

```text
fresh_seed_range = 651001..651256
arm_order = stochastic, expert, learned
requested_run_count = 768
terminal_run_count = 768
shard_count_per_arm = 16
requested_worker_count = 16
actual_worker_count = 16
shards
coverage
mean_terminal_floor_delta
p_positive
learned_act2_entry_count
expert_act2_entry_count
controller_error_count
truncation_count
gate_predicates
wall_clock_seconds
```

`shards` are ordered arm order then shard index `0..15` and record seed start/end,
seed count, completion status, and wall clock. PID/process identity is not
normative. A complete valid report may have `passed=false`, producing Case B.

### Terminal decision — `t075-terminal-decision-report-v1`

Path: `terminal-decision-report.json`.

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
run_head
terminal_case = A|B|C|D
terminal_stage
reached_stages
skipped_stages
stage_report_identities
recommendation
problems
```

`reached_stages` is the canonical prefix through `terminal_stage`.
`skipped_stages` is the remaining suffix. `stage_report_identities` are ordered by
canonical reached-stage order. For A/B terminal stage is EVAL; for C it is GATE;
for D it is the first invalid reached stage. `recommendation` contains exactly one
planner-facing next recommendation; a D recommendation is limited to repairing
the same frozen experiment.

### Final retention — `t075-retention-manifest-v1`

Path: `t075-retention-manifest.json`.

Required fields:

```text
schema_id
schema_version = 1
task_id = T075
run_head
terminal_case
retention_owner = T075
retention_reason
terminal_report_identity
reused_artifacts
produced_artifacts
downstream_consumers
deletion_condition
problems
```

`reused_artifacts` contains the two frozen T065 source identities in stochastic,
expert order. `produced_artifacts` contains every committed reached-stage report
and durable data output in canonical stage order, then role/path order inside a
stage. The final manifest does not recursively rediscover lineage.

## Minimal Semantic Lineage

Required relationships are exactly:

| Output | Required semantic parents |
|---|---|
| SOURCE_REUSE report | PREFLIGHT + exact two frozen T065 source files |
| ownership audit | PREFLIGHT + SOURCE_REUSE report |
| selected states / SELECTION_REPLAY report | PREFLIGHT + SOURCE_REUSE report + ownership rule/audit |
| TARGET table / validation | PREFLIGHT + SELECTION_REPLAY report + selected states |
| TRAIN report/checkpoints | committed valid TARGET report + target table |
| GATE report | TRAIN report + selected checkpoint + target table |
| EVAL report | valid GATE pass + selected checkpoint + frozen fresh seed set |
| terminal report | canonical acceptance state + reached-stage reports |
| final retention manifest | terminal report + identities of committed reached-stage artifacts |

Required parent comparison uses `ArtifactIdentity`. There is no per-stage retention
manifest, recursive proof graph, historical alias resolver, exact command-token
identity, or task-specific PID proof.

## Frozen Durable Output Surface

Repository-relative paths under `artifacts/t075-leakage-safe-non-combat-cohort-repair/`:

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

Temporary data lives only under `ROOT/.tmp/` or another explicitly non-committed
subpath and is never a canonical parent.

## Retention Ownership And Deletion Conditions

T075 owns retention of its produced durable outputs from first committed
StageOutcome until the terminal result is merged or the recovery line is formally
abandoned.

T075 places a consumer hold on the two retained T065 raw sources. It does not take
exclusive ownership and does not delete or rewrite them. The T075 hold is released
only after:

1. a terminal T075 result and final retention manifest are merged, or the Planner
   formally closes T075 without scientific execution;
2. no open/approved task names those source files as required inputs; and
3. no Maintainer reproduction hold remains.

T075-produced large payloads/checkpoints may be deleted after all of the following
are true:

1. the terminal T075 result is merged;
2. `t075-retention-manifest.json` and compact reached-stage reports are retained;
3. no open/approved downstream task consumes the payload;
4. no reproduction hold remains.

Deletion never changes the historical identities recorded in the final retention
manifest.

## Frozen Shard And Worker Plan

The authoritative scientific run uses the 16-logical-core maintainer resource
assumption from repository policy.

### SELECTION_REPLAY

Exactly 16 contiguous selected-state shards:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested and required actual worker count: `16`.

### TARGET

Exactly the same 16 x 20 selected-state shard partition.
Requested and required actual worker count: `16`.

### EVAL

For each arm, exactly 16 contiguous 16-seed shards over `651001..651256`:
for shard `i=0..15`, start=`651001+16*i`, end=`651016+16*i`.
Arm order is stochastic, expert, learned. Requested and required actual worker
count per active arm batch: `16`, with at most 16 concurrent simulator workers.

### Worker-plan failure semantics

If the host cannot establish the required 16-worker plan before a substantial
stage begins, the stage does not start and no StageOutcome is committed. This is
operationally incomplete, not Case D. The Maintainer must resolve the resource
constraint or return a contract/resource gap to the Planner; the implementation
must not silently downgrade authoritative execution to fewer workers.

Each substantial stage records the exact shard ranges, requested/actual worker
count, completion counts, and wall-clock seconds. Worker PID, queue mechanics,
and process binding are explicitly non-semantic.

## Exact Reproduction Commands

The recovery implementation extends the existing neutral module
`sts_combat_rl.commands.non_combat_learning`; it does not add T075 routes to the
legacy flat CLI and does not create a task-numbered production package.

The commands below are the frozen reproducible command surface and stage
arguments. Their semantic arguments, inputs, and outputs are normative. Shell
quoting, token-string identity, launcher formatting, and literal command-text hash
are not scientific evidence and must not be validated by exact string equality.

Common setup after `RUN_HEAD` is frozen:

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

### Local and acceptance gates before scientific execution

```bash
pytest -q tests/test_t075_acceptance.py
pytest -q tests/test_non_combat_learning.py
pytest -q
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
git diff --check
```

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

### TARGET + logical Stage 3 barrier

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

A valid Stage-5 failure atomically commits Case C. EVAL must not run.

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

`finalize` validates and retains the existing canonical terminal state. It never
recomputes A/B/C/D.

## Allowed Implementation Freedom

The Implementer may choose:

- exact class/function names for the canonical types;
- internal JSON field grouping inside `evidence` when all required semantic
  fields remain present;
- atomic-write helper details;
- multiprocessing/process-pool/queue implementation;
- temporary file naming under the uncommitted area;
- reuse of small generic execution helpers already on `main`.

The command layer must remain thin: parse the frozen stage arguments, load strict
parents, invoke one stage adapter, call the canonical acceptance authority, and
persist the resulting artifacts. It must not become a second workflow engine.

## Explicitly Forbidden Recovery Work

Do not:

- cherry-pick or mechanically port the rejected PR #75 orchestration layer;
- preserve its large cluster of task-specific `_t075_*` lifecycle validators as
  the design;
- derive acceptance expected values from production helpers under test;
- add per-stage retention manifests;
- recursively search artifact lineage to rediscover exact inputs;
- search historical aliases for the frozen sources;
- require exact command-string/token equality as scientific evidence;
- treat worker PID/process-binding details as scientific acceptance;
- create a generic workflow framework or task-numbered production package;
- change T075 science to make implementation easier;
- recollect Stage-1 sources;
- reuse PR #75 runtime outputs as authoritative recovery evidence;
- execute Stage 0--6 before the production implementation, A01--A24 boundary, and
  exact `RUN_HEAD` are frozen.

## Selective Salvage Boundary

Safe to consider for salvage after review:

1. the global-ownership scientific primitive and canonical ordering helpers;
2. existing merged T065 strict readers, model-input code, target/training/
   evaluation primitives;
3. implementation-independent acceptance fixtures encoding literal frozen facts;
4. a generic spawn/process primitive only if it contains no T075 acceptance,
   artifact, terminal, or command semantics.

Default rewrite boundary:

- T075 command/orchestration layer;
- T075 terminal/finalization validators;
- T075 command matching;
- T075 path/retention traversal specific to PR #75;
- T075 partial-process/PID evidence machinery;
- acceptance tests coupled to private production helpers.

Anything outside the safe list requires Maintainer proof that it is a bounded
implementation of an already-frozen contract row; otherwise report
`ARCHITECTURE_ESCALATION`.

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
| A09 | TARGET missing/duplicate/nonfinite/wrong action order/continuation seed | D at TARGET |
| A10 | TARGET public-input firewall or semantic parent lineage failure | D at TARGET; TRAIN forbidden |
| A11 | target data exists but Stage-3 barrier/validation outcome not committed | TARGET incomplete; TRAIN forbidden; retry allowed |
| A12 | valid committed TARGET + valid training | GATE reached |
| A13 | valid Stage-5 pass | EVAL reached |
| A14 | valid Stage-5 fail | terminal C; EVAL absent |
| A15 | invalid Stage-5 evidence | terminal D at GATE |
| A16 | valid Stage-6 pass | terminal A |
| A17 | valid Stage-6 fail | terminal B |
| A18 | invalid/missing/truncated/controller-invalid Stage-6 evidence | terminal D at EVAL |
| A19 | initial state has no committed outcomes | current stage exactly PREFLIGHT; no terminal |
| A20 | out-of-order stage, wrong RUN_HEAD, or conflicting duplicate outcome | reject operationally; canonical state and terminal unchanged |
| A21 | interruption before StageOutcome commit | no scientific terminal; same stage may rerun with same RUN_HEAD/parents |
| A22 | committed duplicate is retried, or terminal already committed | no scientific re-execution; idempotent read/validation; A/B/C/D immutable |
| A23 | deployable public model input contains behavior/expert/target/hidden/future field | D at TARGET |
| A24 | command/helper/finalizer disagrees with canonical `advance` authority or final retention fails after terminal | disagreement is IMPLEMENTATION_BUG; retention failure is operational and terminal case unchanged |

A focused implementation regression may be added without changing semantics. A
new semantic scenario or outcome not unambiguously covered above is a
`CONTRACT_GAP`; production changes stop and return to the Planner.

## Verification Sequence

1. Planner contract only; no production code.
2. Maintainer execution-readiness review of this exact contract.
3. Test-only executable A01--A24 boundary.
4. Baseline A01--A24 results against clean pre-implementation `main` where
   meaningful.
5. Maintainer publishes exact-head `SPEC APPROVED` /
   `implementation_authorized=true`.
6. One bounded production implementation pass.
7. Run A01--A24, focused tests, full tests, compile/lint/format/mock gates.
8. Maintainer reviews the full matrix and architecture as one unit.
9. Freeze exact implementation `RUN_HEAD`.
10. Run authoritative T075 stages from that clean head only.
11. Materialize exactly one terminal A/B/C/D and final retention manifest.
12. Planner exact-head scientific/architecture acceptance.
13. Maintainer exact-head implementation/operational acceptance and merge.

No scientific Stage 0--6 execution begins before step 9.

## Review Finding Classification

After implementation starts:

- contract already defines correct behavior and code violates it:
  `IMPLEMENTATION_BUG`;
- correct behavior is not unambiguously defined here: `CONTRACT_GAP`; stop and
  return to Planner;
- successive passes reveal another new cross-module semantic class, duplicated
  lifecycle logic, growing validator glue, or loss of one canonical authority:
  `ARCHITECTURE_ESCALATION`; stop incremental patching.

A corrective pass followed by another newly identified cross-module semantic
class is presumed architecture escalation unless the Maintainer can point to an
existing acceptance row that already defines both behaviors.

## Required PR Evidence

The recovery PR must report:

- this exact approved contract commit and exact implementation `RUN_HEAD`;
- proof PR #75 production orchestration/runtime artifacts were not used as
  authoritative recovery state;
- T065 approved-spec and `sts_lightspeed` integration identities;
- retained T065 source identities and strict validation result;
- raw candidate/group/owner counts and post-owner family/split availability;
- selected 320-state counts and replay result;
- all reached target/training/gate/evaluation metrics;
- exact shard and worker counts/ranges plus wall-clock for substantial stages;
- exact terminal A/B/C/D;
- final artifact identities in `t075-retention-manifest.json`;
- any `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION` raised;
- one next scientific recommendation only after a valid terminal result.

## Final Planner Review Checklist

The Planner will not provide scientific/architectural acceptance unless the exact
final head satisfies all of the following:

- T075 remains scientifically only the global-ownership cohort-partition repair;
- one canonical acceptance transition authority exists in production;
- initial, illegal, retry, duplicate, RUN_HEAD, terminal, and restart semantics
  match this contract;
- terminal A/B/C/D semantics are not duplicated across CLI, validators, and
  finalization helpers;
- B/C remain valid negative science and D remains invalid experiment;
- logical Stage 3 is the atomic TARGET commit barrier;
- artifact schemas contain the required semantic fields without process-manager
  ceremony;
- artifact lineage is explicit and minimal rather than recursive proof machinery;
- one exact `RUN_HEAD` owns authoritative scientific execution;
- acceptance expected values are implementation independent;
- the reference command surface is reproducible without exact-token matching;
- command code remains thin and does not become a hidden workflow engine;
- the frozen 16-shard/16-worker operational protocol is followed and reported;
- PID/queue/process-binding details are not treated as scientific semantics;
- no hidden/human-policy information enters the deployable model;
- no frozen T065 scientific constant changed;
- no authoritative runtime artifact from rejected PR #75 is reused;
- no unreviewed new semantic case was patched locally.

## Lifecycle

This recovery contract remains `DRAFT` until the Main Maintainer performs
execution-readiness review and posts exact-head `SPEC APPROVED` /
`implementation_authorized=true`.

That approval authorizes only bounded implementation against this contract. It
does not authorize the Maintainer or Implementer to redesign T075 semantics.

PR #75 remains the linked unmerged audit record of the rejected architecture.
