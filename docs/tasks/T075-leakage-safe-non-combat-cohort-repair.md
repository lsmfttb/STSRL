# T075: Leakage-Safe Non-Combat Cohort Repair

## Architecture Recovery Declaration

This document is the single normative Planner contract for the T075 recovery line.
It supersedes the unmerged T075 specification/implementation history on PR #75 for
all future implementation and acceptance decisions.

PR #75 remains only an architecture-failure audit record. Its task-specific
orchestration, command-token matching, recursive retention discovery, per-stage
retention machinery, duplicated validators, terminal helpers, PID/process proof,
and runtime artifacts are not accepted project state and must not be used as the
T075 implementation baseline.

The recovery preserves the T075 scientific experiment and replaces the rejected
control plane with one canonical acceptance model, transactional stage commits,
minimal explicit lineage, one frozen scientific RUN_HEAD, and a bounded command
surface.

Architecture recovery base:

`bc9a6790f36ff036f90dc7f03ba0ff026a16788d`

Historical references:

- accepted T065 result: merged task T065;
- rejected T075 implementation/audit line: PR #75;
- previously approved T075 proposal: `e204c5d28cc0bee8013853e8680e8966f5c930a8`.

## Objective And Scientific Boundary

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

The authoritative task index contains `T075 | DRAFT`. It remains DRAFT until the
Main Maintainer publishes exact-head `SPEC APPROVED` with
`implementation_authorized=true`.

Frozen upstream Git identities:

```text
RECOVERY_BASE = bc9a6790f36ff036f90dc7f03ba0ff026a16788d
T065_APPROVED_SPEC = a13c92a66b4d9ad9f6a730293cadc8d66b4a699c
STS_LIGHTSPEED_INTEGRATION = fee272f1ae21c283ad2161f55293cfe6d714134a
```

All three values above use the `git_commit` type defined below, not the `sha256`
content-digest type.

T034, T063, and T066 remain outside T075.

## Information-Regime Boundary

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

Authoritative implementation and scientific execution use:

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
test "$(git rev-parse HEAD)" = "$RUN_HEAD"
```

No authoritative Stage 0-6 execution begins until bounded production
implementation and the implementation-independent A01-A24 suite pass and the
Maintainer freezes one exact implementation commit as `RUN_HEAD`.

A wrong branch, dirty checkout, absent RUN_HEAD, HEAD mismatch, malformed CLI
invocation, or arbitrary wrong input path rejected before a legitimate stage
adapter begins is an operational invocation failure. It commits no StageOutcome
and creates no A/B/C/D result.

If production code changes after authoritative scientific execution starts, the
old RUN_HEAD is retired. The Maintainer identifies the earliest semantically
affected stage, reruns the acceptance suite, freezes a new RUN_HEAD, and reruns
that stage plus downstream stages. PR #75 runtime outputs are never authoritative
recovery evidence.

## Frozen T065 Source Inputs

T075 reuses exactly two retained T065 raw source files and never recollects them.
Their T075 `ArtifactIdentity.role` is frozen to `current_output`, matching the
retained T065 artifact role.

| Arm | role | Relative path | Bytes | SHA-256 |
|---|---|---|---:|---|
| stochastic | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| expert | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

Both files must pass the current strict T065 source reader and match:

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

Missing, unreadable, hash/size/role-invalid, strict-reader-invalid, or
metadata-invalid exact input makes SOURCE_REUSE invalid and therefore Case D at
SOURCE_REUSE. Such a failure is represented by the frozen SOURCE_REUSE source-check
records below; it is not converted into a pre-stage invocation rejection.
Recollection, alternate aliases, basename search, recursive manifest discovery,
and replacement are forbidden.

## Frozen Source And Split Constants

- player: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- source seeds: `650001..650256`;
- source driver seed: `654001`;
- source arms: stochastic and expert retained files above;
- battle controller provenance: `oracle_search_v1_highest_mean_s20`.

Seed-derived splits:

- train: `650001..650154`;
- validation: `650155..650205`;
- heldout: `650206..650256`.

No simulator seed may change split.

Canonical family order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas:

- train: 48;
- validation: 16;
- heldout: 16.

A valid cohort contains exactly 320 selected states.

## Public Model Input

Use `non-combat-model-input-v1` exactly:

- tactical snapshot dimension: 4634;
- public context dimension: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- no behavior/expert/target/outcome/hidden/future feature;
- training-split-only CPU float32 population normalization;
- population std clamped to at least 1.0 and checkpointed unchanged.

## T075 Scientific Primitive: Global Replay Ownership

Selectable candidates must:

- pass the strict `t065-source-state-v1` reader;
- come from a problem-free terminal source run;
- belong to a mandatory family;
- retain the split implied by simulator seed;
- retain source provenance;
- pass existing T065 public/model/action/replay validation.

Malformed/provenance-invalid rows fail closed. Nonterminal/truncated rows remain
source evidence but are not selectable.

Replay equivalence is unchanged:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical candidate bytes use UTF-8 canonical JSON with sorted keys, compact
separators, `ensure_ascii=False`, and `allow_nan=False`.

Member order is unchanged T065:

```text
selection_digest = sha256(
    b"T065-source-selection-v1\n" + canonical_candidate_json_bytes
).hexdigest()
member_order_key = (selection_digest, canonical_candidate_json_bytes)
```

Replay-group digest:

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

Algorithm:

1. admit all selectable candidates across both retained arms and all frozen splits;
2. group globally by unchanged replay equivalence;
3. sort each group by complete `member_order_key`;
4. if distinct source rows have identical complete member-order keys, fail D at
   SELECTION_REPLAY; no extra tie breaker is allowed;
5. otherwise the first member is the sole owner;
6. exclude all non-owners before quota selection;
7. retain the owner's seed-derived split;
8. within each `(family, split)` owner bucket, sort by the same order and take
   exactly 48/16/16.

If any owner bucket is below quota, fail D at SELECTION_REPLAY. There is no
recollection, scale increase, split reassignment, balancing, target-aware
selection, manual replacement, or replay-key change.

A valid selected cohort has exactly 320 states, exact family/split quotas, unique
selected replay keys, zero cross-split replay overlap, zero seed split leakage,
exact replay of every selected public/model state and ordered legal actions, and
zero replacement after replay failure.

## Unchanged Downstream Science

### Counterfactual Targets

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
hidden-future resampling.

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
- validation q_floor MAE selects checkpoint;
- exact MAE tie selects lower seed.

### Stage-5 Gate

Use 64 heldout states. A valid Stage-5 report passes iff all hold:

1. aggregate mean paired `q_floor(model)-q_floor(expert) > 0`;
2. median paired delta `>= 0`;
3. at least 3/4 family means `>= 0`;
4. 10,000-stratified-bootstrap `p_positive >= 0.90` using
   `random.Random(655001)`;
5. non-selected model-seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violation.

Valid failure is Case C and EVAL is skipped. Invalid evidence is D at GATE.

### Stage-6 Gate

Run only after valid Stage-5 pass.

- fresh seeds `651001..651256`;
- driver/fallback seed `654002`;
- arm order: stochastic, expert, learned-with-expert-fallback;
- 16 fixed shards x 16 seeds per arm;
- 768 valid terminal runs required;
- bootstrap 10,000 matched-seed resamples with `random.Random(655002)`;
- coverage `L/D >= 0.60`, `F/M <= 0.01`, `D != 0`, `M != 0` using unchanged
  T065 D/L/M/F definitions.

Valid Stage-6 passes iff all hold:

1. matched mean terminal-floor delta `> 0`;
2. bootstrap `p_positive >= 0.80`;
3. learned Act-2 entry count `>=` expert;
4. zero controller errors and unreported truncations;
5. coverage passes;
6. stronger signal: learned Act-2 count `>` expert OR `p_positive >= 0.95`.

Valid pass -> A. Valid fail -> B. Invalid Stage-6 evidence -> D at EVAL.

## Canonical Type System

The contract distinguishes Git object identity from content digest identity.

```text
git_commit = lowercase hexadecimal string of exactly 40 characters
sha256 = lowercase hexadecimal string of exactly 64 characters
string = JSON string
bool = JSON true|false
int = JSON integer, not bool
nonneg_int = int >= 0
number = finite JSON integer or float
Stage = PREFLIGHT | SOURCE_REUSE | SELECTION_REPLAY | TARGET | TRAIN | GATE | EVAL
TerminalCase = A | B | C | D
Family = MAP_SCREEN | REST_ROOM | REWARDS | TREASURE_ROOM
Split = train | validation | heldout
Status = passed | failed
Promotion = experimental_public_with_expert_fallback | no_promotion
RecommendationCode = review_joint_policy_next_step | narrow_transfer_followup | close_v1_no_followup | narrow_target_model_diagnostic | rerun_same_experiment_after_narrow_repair
SourceFailureClass = none | missing | unreadable | identity_mismatch | strict_reader_invalid | metadata_invalid
```

`RUN_HEAD`, `RECOVERY_BASE`, `T065_APPROVED_SPEC`, and
`STS_LIGHTSPEED_INTEGRATION` are `git_commit`.

Selection digests, replay-group digests, candidate-content digests, and artifact
content hashes are `sha256`.

## ArtifactIdentity

Serialized exactly as:

```json
{"role":"string","path":"string","sha256":"<64hex>","size_bytes":0}
```

Rules:

- `role` is a non-empty string frozen by the producing/consuming schema;
- `path` is repository-relative POSIX under `artifacts/`;
- normalize backslashes to `/`, remove `.` components and one leading `./`;
- reject `..`;
- case-sensitive comparison;
- basename-only matching forbidden;
- `size_bytes` is `nonneg_int`.

Frozen role names:

```text
current_output             # both reused T065 raw source parents
preflight_report
source_reuse_report
ownership_audit
selected_states
target_table
target_validation_report
checkpoint
training_report
gate_report
eval_report
terminal_report
retention_manifest
```

ArtifactIdentity equality compares all four fields.

## Canonical Acceptance Model

T075 has one production-side acceptance authority. CLI handlers, readers,
validators, persistence, and finalization must not implement independent transition
logic.

Conceptual model:

```text
StageOutcome =
  schema_id
  schema_version
  task_id
  run_head: git_commit
  stage: Stage
  valid: bool
  passed: bool
  parents: tuple[ArtifactIdentity]
  outputs: tuple[ArtifactIdentity]
  evidence: exact stage-specific object
  problems: tuple[string]

CommittedOutcome =
  stage: Stage
  report_identity: ArtifactIdentity

AcceptanceState =
  run_head: git_commit
  committed_outcomes: ordered tuple[CommittedOutcome]
  current_stage: Stage | None
  terminal_case: TerminalCase | None
  terminal_stage: Stage | None
```

There is one pure/effectively pure transition authority:

```text
advance(AcceptanceState, StageOutcome) -> AcceptanceState
```

`outcome_identity(outcome)` is the ArtifactIdentity of the canonical serialized
StageOutcome bytes at that stage's frozen report path and frozen report role.
The report does not contain its own identity, so there is no self-reference.

Initial state:

```text
run_head = RUN_HEAD
committed_outcomes = ()
current_stage = PREFLIGHT
terminal_case = None
terminal_stage = None
```

Durable state is reconstructed only by reading committed StageOutcome report files
in canonical stage order, computing each exact report identity, and replaying them
through `advance`. There is no mutable workflow-state file and no second transition
authority.

### Legal Scientific Transitions

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

For PREFLIGHT, SOURCE_REUSE, SELECTION_REPLAY, TARGET, TRAIN,
`valid=true, passed=false` is illegal.

Poor learned-policy performance alone may produce B or C, never D.

### Transition Precedence

For every candidate StageOutcome, `advance` applies exactly:

1. reject if `outcome.run_head != state.run_head`;
2. compute candidate report identity from the final canonical StageOutcome;
3. if ledger already contains `outcome.stage`, handle duplicate before terminal or
   current-stage checks:
   - identical report identity -> idempotent existing state;
   - different report identity -> operational conflicting duplicate, state unchanged;
4. if terminal already exists, reject any new uncommitted stage, state unchanged;
5. require `outcome.stage == state.current_stage`;
6. require exact legal `(valid, passed)` combination and validate parents by the
   canonical parent rule below;
7. apply the transition table;
8. append the candidate report identity to the ledger;
9. if terminal, set `terminal_case`, `terminal_stage`, `current_stage=None`; else
   advance to next stage.

Out-of-order/wrong-RUN_HEAD/conflicting duplicate are operational rejection, not D.

### Canonical Parent Validation

For every stage, previously committed StageOutcome report/output parents must match
the canonical ledger in the exact frozen order. Same-stage sibling outputs are
never parents.

SOURCE_REUSE has one closed-world special rule because it validates two frozen
external inputs whose failure must itself be representable as scientific/fidelity
evidence:

1. before SOURCE_REUSE work begins, the only already-committed parent that must
   validate is the committed PREFLIGHT report;
2. the two T065 source identities in `Frozen T065 Source Inputs` are frozen
   **expected external inputs**, not automatically accepted semantic parents;
3. SOURCE_REUSE inspects exactly those two expected paths, in stochastic/expert
   order, and emits exactly two `SourceRecord` checks;
4. for `SOURCE_REUSE valid=true, passed=true`, both observed artifacts must equal
   the corresponding expected identities in all four fields and all strict-reader
   and metadata checks must pass; only then are the two validated source identities
   legal StageOutcome parents, with parents exactly `[PREFLIGHT, stochastic source,
   expert source]`;
5. for `SOURCE_REUSE valid=false, passed=false`, parents are exactly `[PREFLIGHT]`;
   at least one `SourceRecord` must fail, and the failed expected external inputs
   remain evidence only rather than semantic parents;
6. canonical `advance` must accept that invalid SOURCE_REUSE parent shape and apply
   the normal `SOURCE_REUSE invalid -> D at SOURCE_REUSE` transition.

No alias, alternate path, basename match, manifest discovery, replacement source,
or arbitrary external parent is legal. The two frozen expected T065 identities are
the complete external-input universe for SOURCE_REUSE.

For every stage after SOURCE_REUSE, every parent must resolve in the exact frozen
order to a report/output identity already present in the previously committed T075
ledger.

## Transactional Stage Commit

This ordering is normative and resolves report/output identity causality.

For a legitimately reached stage:

1. validate checkout, RUN_HEAD, current canonical state, and all already-committed
   parents required to begin that stage; SOURCE_REUSE begins with PREFLIGHT only
   and validates its two frozen expected external inputs during stage work;
2. write expensive/intermediate prospective outputs under `ROOT/.tmp/`;
3. run all stage-specific completeness/fidelity checks and determine the final
   stage-specific parent shape, including SOURCE_REUSE's conditional valid/invalid
   parent rule;
4. if the stage is successful, atomically promote each validated output to its
   deterministic frozen final path and compute its final ArtifactIdentity;
   if the stage is invalid, promote no successful data output and use `outputs=[]`;
5. construct the **final** StageOutcome including final parent/output identities and
   final evidence/problems;
6. canonical-serialize that final StageOutcome for its frozen report path, compute
   the prospective report ArtifactIdentity, and call canonical `advance` on the
   final outcome; this is a pure prospective check and creates no durable state;
7. atomically write exactly those canonical StageOutcome bytes to the frozen report
   path; the StageOutcome report write is the stage commit marker;
8. only after successful report write, reconstruct/advance durable state from the
   committed report identity;
9. if terminal, atomically materialize the unique terminal report from canonical
   state.

There is no provisional StageOutcome identity and no second transition path.

If output promotion in step 4 succeeds but report commit in step 7 is interrupted,
those final-path outputs are uncommitted. They are ignored as parents and may be
deterministically overwritten on retry. No scientific terminal result exists.

If the report bytes successfully commit, that outcome is immutable scientific /
fidelity evidence and is not rerun to obtain a more favorable result.

## TARGET / Logical Stage-3 Barrier

Logical Stage 3 is inside TARGET, not a separate execution stage.

The prospective target payload remains temporary until reopened and checked in
exact order:

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

If all pass, promote target table, compute target-table identity, and commit TARGET
`valid=true, passed=true` with that identity in outputs.

If any completed check fails, promote no target table and atomically commit the
TARGET report with:

```text
valid=false
passed=false
outputs=[]
stage3_barrier_passed=false
problems=non-empty
```

Canonical advance then yields D at TARGET and TRAIN is forbidden.

Interruption before the StageOutcome report commit is distinct: TARGET is
uncommitted, no terminal exists, and retry from the same committed parents is
allowed.

## Selection Same-Stage Derivation And Lineage

Ownership audit and selected-state JSONL are sibling outputs of one
SELECTION_REPLAY transaction. The ownership audit is **not** a committed parent of
the selected-state file and is not a separate StageOutcome.

Within the stage transaction:

```text
committed parents:
  PREFLIGHT report
  SOURCE_REUSE report
       |
       v
candidate domain -> ownership computation -> ownership audit
                                      |
                                      v
                              quota selection -> selected states -> replay checks
```

Only after both prospective sibling outputs and all replay checks are valid are
they promoted and their final identities inserted into the single
SELECTION_REPLAY StageOutcome.

Therefore the SELECTION_REPLAY StageOutcome parents are exactly:

1. PREFLIGHT report identity;
2. SOURCE_REUSE report identity.

Its outputs are exactly:

1. ownership audit identity;
2. selected-state JSONL identity.

The selected-state derivation from the ownership computation is scientific
same-stage evidence, not ArtifactIdentity parentage. No prior ownership commit
boundary is created.

## Canonical JSON And Exact Shared Records

All T075 JSON control/report artifacts use UTF-8 canonical JSON:

```text
sort_keys=True
separators=(',', ':')
ensure_ascii=False
allow_nan=False
one trailing newline
```

Unknown top-level keys in T075 v1 report schemas are rejected. Existing unchanged
T065 scientific payloads retain their merged strict T065 schemas.

Shared records:

```text
CheckRecord = {name:string,status:Status,counts:{string:nonneg_int},problems:[string]}
RangeRecord = {shard_index:nonneg_int,start:int,end:int,count:nonneg_int,wall_clock_seconds:number}
PredicateRecord = {name:string,passed:bool}
FamilyValue = {family:Family,value:number}
FamilySplitCount = {family:Family,split:Split,count:nonneg_int}
SplitCount = {split:Split,count:nonneg_int}
HistogramBin = {group_size:nonneg_int,group_count:nonneg_int}
```

SourceRecord serialized keys exactly:

```text
arm: stochastic_non_combat_v1 | expert_non_combat_v1
expected_artifact: ArtifactIdentity
observed_artifact: ArtifactIdentity | null
strict_reader_passed: bool
metadata_passed: bool
failure_class: SourceFailureClass
seed_start: int | null
seed_end: int | null
requested_run_count: nonneg_int | null
terminal_run_count: nonneg_int | null
truncated_run_count: nonneg_int | null
failed_run_count: nonneg_int | null
shard_count: nonneg_int | null
worker_count: nonneg_int | null
controller: string | null
approved_spec_commit: git_commit | null
sts_lightspeed_commit: git_commit | null
problems: [string]
```

`expected_artifact` is always the exact frozen literal for that arm.
`observed_artifact=null` is allowed only when a readable artifact identity cannot
be obtained. Metadata fields are populated when derivable from readable content and
are otherwise `null`; a valid source record has no null metadata fields.

`failure_class` is deterministic with this precedence:

1. `missing` when the frozen path does not exist;
2. `unreadable` when the path exists but a complete readable artifact identity
   cannot be obtained;
3. `identity_mismatch` when the observed four-field identity differs from the
   expected literal;
4. `strict_reader_invalid` when identity matches but the strict T065 reader fails;
5. `metadata_invalid` when identity/strict reader pass but any frozen metadata
   check fails;
6. `none` only when all identity, strict-reader, and metadata checks pass.

The two SOURCE_REUSE records are always present in stochastic/expert order, even
when one or both sources fail. A failed record has non-empty `problems`; a passing
record has `problems=[]`.

OwnershipMember keys exactly:

```text
source_arm: stochastic_non_combat_v1 | expert_non_combat_v1
simulator_seed: int
split: Split
family: Family
selection_digest: sha256
candidate_sha256: sha256
owner: bool
```

`candidate_sha256 = sha256(canonical_candidate_json_bytes)` is audit identity only,
never a tie breaker.

OwnershipGroup keys exactly:

```text
group_digest: sha256
family: Family
member_count: nonneg_int
cross_split: bool
members: [OwnershipMember]
```

Members are ordered by complete frozen `member_order_key`; a valid non-tie group
has exactly one owner.

PerSeedMetric:

```text
model_seed: 653001 | 653002
validation_mae: number
checkpoint: ArtifactIdentity(role=checkpoint)
```

EvalShardRecord:

```text
arm: stochastic | expert | learned
shard_index: 0..15
seed_start: int
seed_end: int
seed_count: 16
terminal_run_count: nonneg_int
status: Status
wall_clock_seconds: number
```

CoverageRecord:

```text
D: nonneg_int
L: nonneg_int
M: nonneg_int
F: nonneg_int
L_over_D: number
F_over_M: number
passed: bool
```

All numeric metrics are finite.

## Common StageOutcome Envelope

Every committed stage report has exactly:

```text
schema_id: string
schema_version: 1
task_id: T075
run_head: git_commit
stage: Stage
valid: bool
passed: bool
parents: [ArtifactIdentity]
outputs: [ArtifactIdentity]
evidence: exact stage object
problems: [string]
```

Successful pre-gate stage: `valid=true`, `passed=true`, `problems=[]`.
Invalid stage: `valid=false`, `passed=false`, `problems` non-empty.
Valid GATE/EVAL negative: `valid=true`, `passed=false` and therefore C/B.

Frozen report path/role/schema mapping:

| Stage | Path | role | schema_id |
|---|---|---|---|
| PREFLIGHT | `stage0-preflight.json` | `preflight_report` | `t075-preflight-report-v1` |
| SOURCE_REUSE | `stage0-source-reuse.json` | `source_reuse_report` | `t075-source-reuse-report-v1` |
| SELECTION_REPLAY | `stage1-selection-report.json` | `selected_states` is not report role; report role is `selection_report` | `t075-selection-report-v1` |
| TARGET | `stage2-validation.json` | `target_validation_report` | `t075-target-validation-report-v1` |
| TRAIN | `stage4-training-report.json` | `training_report` | `t075-training-report-v1` |
| GATE | `stage5-heldout-report.json` | `gate_report` | `t075-stage5-report-v1` |
| EVAL | `stage6-complete-run-report.json` | `eval_report` | `t075-stage6-report-v1` |

`selection_report` is additionally a frozen valid ArtifactIdentity role for the
SELECTION_REPLAY report.

## Stage Schemas And Parent/Output Contracts

### PREFLIGHT

Parents `[]`; outputs `[]`.

Evidence exact keys:

```text
recovery_base: git_commit
t065_approved_spec_commit: git_commit
sts_lightspeed_integration_commit: git_commit
simulator_identity: string
model_input_schema: string
checks: [CheckRecord]
```

Check order:

1. runtime_imports
2. simulator_identity
3. checkpoint_roundtrip
4. frozen_controller_action_space
5. model_input_schema_dimensions
6. public_input_firewall_capability
7. torch_runtime

### SOURCE_REUSE

Before source inspection, the only committed parent is the PREFLIGHT report.
Evidence always contains exactly two `SourceRecord` values in stochastic/expert
order, each anchored to its exact frozen `expected_artifact` literal.

For `valid=true, passed=true`, parents exact order is:

1. PREFLIGHT report;
2. validated stochastic T065 source, whose observed identity equals its expected
   `current_output` identity;
3. validated expert T065 source, whose observed identity equals its expected
   `current_output` identity.

Both records must have `failure_class=none`, `strict_reader_passed=true`,
`metadata_passed=true`, exact observed/expected identity equality, and complete
non-null frozen metadata.

For `valid=false, passed=false` / A02, parents are exactly:

1. PREFLIGHT report.

At least one of the two records must have `failure_class != none`; failed expected
sources remain source-check evidence only and are not StageOutcome parents. This
invalid outcome is a normal committed SOURCE_REUSE StageOutcome and transitions to
D at SOURCE_REUSE.

Outputs `[]` in both forms.

Evidence exact keys:

```text
sources: [SourceRecord]  # exactly stochastic then expert
validation_passed: bool
```

`validation_passed=true` iff both source records pass all frozen identity,
strict-reader, and metadata checks. For SOURCE_REUSE it must equal both
StageOutcome booleans: `validation_passed == valid == passed`.

### Ownership Audit Data Artifact

Path `stage1-ownership-audit.json`, role `ownership_audit`, schema
`t075-ownership-audit-v1`.

It is a same-stage data output, not a StageOutcome. It has exact top-level keys:

```text
schema_id
schema_version=1
task_id=T075
run_head: git_commit
preflight_report: ArtifactIdentity
source_reuse_report: ArtifactIdentity
selection_strategy_id=leakage-safe-global-owner-v1
replay_identity: string
group_domain=T075-replay-group-v1
candidate_domain_counts: [FamilySplitCount]
group_count: nonneg_int
singleton_group_count: nonneg_int
non_singleton_group_count: nonneg_int
cross_split_group_count: nonneg_int
excluded_non_owner_count: nonneg_int
group_size_histogram: [HistogramBin]
owner_counts_by_family_split: [FamilySplitCount]
groups: [OwnershipGroup]
problems: [string]
```

This artifact records provenance references but does not create a prior committed
parent boundary.

Ordering: canonical family order, split train/validation/heldout, histogram by
ascending group size, groups by ascending group_digest, members by member order.

### SELECTION_REPLAY

Parents exact order: PREFLIGHT report, SOURCE_REUSE report.

Outputs exact order:

1. ownership audit (`ownership_audit`);
2. selected states JSONL (`selected_states`).

Selected-state JSONL contains exactly one complete strict current
`t065-source-state-v1` object per line, selected-state indices 0..319, final newline,
no wrapper.

Evidence:

```text
post_owner_available_counts: [FamilySplitCount]
selected_count: 320
selected_counts_by_family_split: [FamilySplitCount]
selected_replay_identity_digests: [sha256]
replay:
  shard_count: 16
  requested_worker_count: 16
  actual_worker_count: 16
  ranges: [RangeRecord]
  attempted: 320
  restored: 320
  mismatch_count: 0
  replacement_count: 0
  duplicate_count: 0
  cross_split_overlap_count: 0
  wall_clock_seconds: number
```

Range order shard 0..15.

### TARGET

Target table path `stage2-target-table.json`, role `target_table`, unchanged strict
T065 schema `t065-counterfactual-target-table-v1` version 1.

TARGET report parents exact order:

1. PREFLIGHT report;
2. SELECTION_REPLAY report;
3. selected-state JSONL output.

Successful outputs: target table only. Invalid outputs: `[]`.

Evidence:

```text
selected_state_count: 320
target_row_count: nonneg_int
eligible_action_count: nonneg_int
family_split_state_counts: [FamilySplitCount]
continuation_replication_counts_by_split: [SplitCount]
shard_count: 16
requested_worker_count: 16
actual_worker_count: 16
ranges: [RangeRecord]
checks: [CheckRecord]  # exact 10 barrier names/order
violation_counts: {string:nonneg_int}
stage3_barrier_passed: bool
wall_clock_seconds: number
```

### TRAIN

Parents exact order: TARGET validation report, target table.

Successful outputs: two checkpoint identities ordered model seed 653001 then
653002, each role `checkpoint`. Invalid TRAIN promotes no checkpoints and outputs
`[]`.

Evidence:

```text
model_seeds: [653001,653002]
training_config: object equal to frozen T065 training config
normalizer_provenance: string
per_seed_metrics: [PerSeedMetric]  # seed order
selected_model_seed: 653001|653002
selected_checkpoint: ArtifactIdentity(role=checkpoint)
wall_clock_seconds: number
```

### GATE

Parents exact order: TRAIN report, selected checkpoint, target table. Outputs `[]`.

Evidence:

```text
heldout_state_count: 64
selected_model_seed: 653001|653002
non_selected_model_seed: 653001|653002
mean_paired_delta: number
median_paired_delta: number
family_mean_deltas: [FamilyValue]
p_positive: number
non_selected_mean_paired_delta: number
violation_counts: {string:nonneg_int}
gate_predicates: [PredicateRecord]
wall_clock_seconds: number
```

Predicate order is the six Stage-5 conditions above.

### EVAL

Exists only after valid GATE pass.

Parents exact order: GATE report, selected checkpoint. Outputs `[]`.

Evidence:

```text
fresh_seed_start: 651001
fresh_seed_end: 651256
arm_order: [stochastic,expert,learned]
requested_run_count: 768
terminal_run_count: 768
shard_count_per_arm: 16
requested_worker_count: 16
actual_worker_count: 16
shards: [EvalShardRecord]
coverage: CoverageRecord
mean_terminal_floor_delta: number
p_positive: number
learned_act2_entry_count: nonneg_int
expert_act2_entry_count: nonneg_int
controller_error_count: nonneg_int
truncation_count: nonneg_int
gate_predicates: [PredicateRecord]
wall_clock_seconds: number
```

Shard order arm order then shard index. Predicate order is the six Stage-6
conditions above.

## Terminal Decision

Single path `terminal-decision-report.json`, role `terminal_report`, schema
`t075-terminal-decision-report-v1`.

Exact keys:

```text
schema_id
schema_version=1
task_id=T075
run_head: git_commit
terminal_case: A|B|C|D
terminal_stage: Stage
reached_stages: [Stage]
skipped_stages: [Stage]
stage_report_identities: [ArtifactIdentity]
promotion: Promotion
recommendation_code: RecommendationCode
recommendation: string
problems: [string]
```

Reached stages are canonical prefix through terminal_stage; skipped stages are
remaining suffix; report identities follow reached-stage order.

A/B terminal_stage EVAL; C terminal_stage GATE; D terminal_stage first invalid
reached stage.

Terminal promotion/recommendation semantics preserve the frozen T065 successor
boundary. Every terminal report contains exactly one planner-facing **disposition**;
the disposition may explicitly close a line with no successor task.

- **A / EVAL**: `promotion=experimental_public_with_expert_fallback`;
  `recommendation_code=review_joint_policy_next_step`; the disposition is to review
  T066 or one narrower joint-policy task. This is not a natural-A20 or live-game
  promotion claim.
- **B / EVAL**: `promotion=no_promotion`;
  `recommendation_code=narrow_transfer_followup`; one narrow follow-up is selected
  from observed screen coverage, target-horizon/rollout-policy mismatch, or
  run-distribution shift. Do not authorize a larger natural run merely because the
  256 fresh seeds are neutral.
- **C / GATE**: `promotion=no_promotion`; EVAL/Stage 6 is skipped and the v1
  formulation is closed. `recommendation_code` is exactly one of:
  - `close_v1_no_followup`: close v1 with no successor diagnostic; or
  - `narrow_target_model_diagnostic`: recommend one narrow target/model diagnostic
    justified by the observed valid Stage-5 failure.
  There may never be more than one follow-up diagnostic. This preserves T065's
  **at most one** diagnostic boundary rather than requiring a successor task.
- **D / first invalid reached stage**: `promotion=no_promotion`;
  `recommendation_code=rerun_same_experiment_after_narrow_repair`; no policy
  conclusion is allowed; the disposition names one narrow repair necessary to
  rerun the same frozen experiment; every downstream scientific stage is skipped.

`recommendation` is descriptive text constrained by the terminal case and
`recommendation_code`; it is not a second decision authority. For
`close_v1_no_followup`, it describes closure/no follow-up rather than inventing a
successor diagnostic.

The first valid terminal state implied by committed StageOutcome ledger is
immutable. If terminal report write is interrupted after terminal-producing stage
commit, restart reconstructs exact state and materializes the same report. A
conflicting terminal file is operational integrity failure and cannot reinterpret
science.

## Final Retention

Path `t075-retention-manifest.json`, role `retention_manifest`, schema
`t075-retention-manifest-v1`.

Exact keys:

```text
schema_id
schema_version=1
task_id=T075
run_head: git_commit
terminal_case: A|B|C|D
retention_owner=T075
retention_reason: string
terminal_report_identity: ArtifactIdentity(role=terminal_report)
reused_artifacts: [ArtifactIdentity]
produced_artifacts: [ArtifactIdentity]
downstream_consumers: [string]
deletion_condition: [string]
problems: [string]
```

Reused artifacts are the exact two T065 sources in stochastic/expert order with
role `current_output`. Produced artifacts contain every committed reached-stage
report and durable data output in canonical stage order, then role/path order.
No recursive provenance discovery.

T075 holds reused T065 sources until terminal result/manifest merge or formal T075
abandonment, no open/approved consumer remains, and no Maintainer reproduction hold
remains. T075-produced large payloads may be deleted only after terminal merge,
compact reports/retention manifest remain, no downstream consumer remains, and no
reproduction hold remains. Historical identities are never rewritten.

## Minimal Semantic Lineage

Previously committed T075 report/output identities are the normal semantic-parent
source. SOURCE_REUSE has the one closed-world external-input exception defined
above, and its parent shape depends on whether those expected inputs validate.
Same-stage sibling outputs may refer to one another only as internal derivation /
evidence, never as committed parents.

| Output | Committed semantic parents |
|---|---|
| SOURCE_REUSE valid report | committed PREFLIGHT + exact two successfully validated frozen T065 source identities |
| SOURCE_REUSE invalid/A02 report | committed PREFLIGHT only; failed expected source identities remain evidence |
| SELECTION_REPLAY report | PREFLIGHT + SOURCE_REUSE report |
| ownership audit + selected states | produced atomically inside SELECTION_REPLAY; no parent relation between siblings |
| TARGET report/table | PREFLIGHT + committed SELECTION_REPLAY report + committed selected-states output |
| TRAIN report/checkpoints | committed valid TARGET report + target table |
| GATE report | TRAIN report + selected checkpoint + target table |
| EVAL report | valid GATE pass report + selected checkpoint |
| terminal report | canonical committed StageOutcome ledger |
| final retention | terminal report + identities of committed reached-stage artifacts |

The two T065 expected identities are never discovered or substituted. On successful
SOURCE_REUSE they become exact semantic parents only after observed identity,
strict-reader, and metadata validation succeeds. On A02 they remain evidence only,
allowing the invalid StageOutcome to commit D without opening a generic external
parent mechanism.

No per-stage retention manifest, recursive proof graph, historical alias resolver,
exact command-token identity, or task-specific PID proof.

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

Temporary data belongs under `ROOT/.tmp/` and is never a canonical parent.

## Frozen Shard And Worker Plan

Authoritative execution uses the repository's 16-logical-core resource assumption.

SELECTION_REPLAY and TARGET use exactly 16 contiguous 20-state shards:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested and actual worker count: 16.

EVAL uses, per arm, 16 contiguous 16-seed shards over 651001..651256:

```text
start(i)=651001+16*i
end(i)=651016+16*i
```

Arm order stochastic, expert, learned. Requested/actual worker count per active arm
batch 16; at most 16 concurrent simulator workers.

If the host cannot establish required worker plan before substantial stage work,
stage does not start and commits no StageOutcome. This is operationally incomplete,
not Case D. Do not silently downgrade workers. Record exact ranges, requested/
actual workers, completion counts, and wall clock. PID/queue/process binding is
non-semantic.

## Exact Reproduction Commands

The recovery extends neutral `sts_combat_rl.commands.non_combat_learning`; no
T075-numbered production package or generic workflow framework.

Reference commands freeze semantic inputs/outputs/arguments. Shell quoting,
literal token strings, and command-text hashes are not acceptance evidence.

Common environment:

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

Local/acceptance gates all use pinned interpreter:

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

If pinned PY lacks a required module, readiness fails; do not substitute another
interpreter.

PREFLIGHT:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning preflight \
  --output "$ROOT/stage0-preflight.json" \
  --simulator-runtime --torch-runtime --sim-seed 1 --ascension 20 \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

SOURCE_REUSE:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning validate-reuse \
  --source "$T065/source-stochastic-650001-650256-c57b2ee.json" \
  --source "$T065/source-expert-650001-650256-deeaa46.json" \
  --preflight "$ROOT/stage0-preflight.json" \
  --output "$ROOT/stage0-source-reuse.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

No T075 collect command exists.

SELECTION_REPLAY:

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

TARGET:

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

TRAIN:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning train \
  --target-table "$ROOT/stage2-target-table.json" \
  --target-validation "$ROOT/stage2-validation.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage4-training-report.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

GATE:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning gate \
  --target-table "$ROOT/stage2-target-table.json" \
  --training-report "$ROOT/stage4-training-report.json" \
  --checkpoint-directory "$ROOT/stage4-checkpoints" \
  --output "$ROOT/stage5-heldout-report.json" \
  --run-head "$RUN_HEAD" \
  --terminal-report "$ROOT/terminal-decision-report.json"
```

EVAL:

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

Finalization:

```bash
$PY -m sts_combat_rl.commands.non_combat_learning finalize \
  --artifact-root "$ROOT" \
  --terminal-report "$ROOT/terminal-decision-report.json" \
  --retention-manifest "$ROOT/t075-retention-manifest.json" \
  --run-head "$RUN_HEAD"
```

Finalize validates/retains existing canonical terminal state and never recomputes
A/B/C/D.

## Allowed Implementation Freedom

Allowed:

- exact Python class/function names implementing canonical types;
- atomic-write helper details consistent with the transaction ordering above;
- multiprocessing/process-pool implementation;
- temporary filenames under uncommitted area;
- bounded reuse of neutral merged helpers.

Not allowed:

- another workflow/transition authority;
- task-specific command-token equality;
- PID/process binding as acceptance science;
- recursive retention/provenance discovery;
- per-stage retention manifests;
- task-numbered production package or generic workflow framework;
- PR #75 orchestration/runtime outputs as authoritative state;
- recollection or scientific-constant changes;
- acceptance expected values generated by production helpers under test.

## Normative Acceptance Matrix

Before production implementation, the Maintainer translates A01-A24 into an
implementation-independent executable test-only boundary. Expected literals and
fixtures must not be generated by production code under test.

| ID | Scenario | Required result |
|---|---|---|
| A01 | exact frozen expected/observed source identities/roles/metadata | SOURCE_REUSE pass; parents `[PREFLIGHT, stochastic source, expert source]` |
| A02 | missing/unreadable/hash/size/role/strict-reader/metadata-invalid frozen source | committed D at SOURCE_REUSE; parents `[PREFLIGHT]`; exactly two source-check records retained; at least one failure |
| A03 | cross-split replay-equivalent raw candidates | deterministic global owner; not itself error |
| A04 | exact full member-order tie between distinct rows | D at SELECTION_REPLAY |
| A05 | owner bucket below quota | D at SELECTION_REPLAY |
| A06 | selected duplicate/cross-split replay overlap | D at SELECTION_REPLAY |
| A07 | all 320 selected states replay exactly under fixed 16x20/16-worker plan | SELECTION_REPLAY pass |
| A08 | one selected replay mismatch | D; no replacement |
| A09 | TARGET missing/duplicate/nonfinite/wrong action order/continuation seed | D at TARGET |
| A10 | TARGET public-input firewall or committed semantic lineage failure | D at TARGET; TRAIN forbidden |
| A11 | target/intermediate data exists but TARGET StageOutcome report did not commit | TARGET incomplete; retry allowed; no terminal |
| A12 | valid committed TARGET + valid training | GATE reached |
| A13 | valid Stage-5 pass | EVAL reached |
| A14 | valid Stage-5 fail | terminal C; EVAL absent; close v1 with no promotion and at most one narrow diagnostic |
| A15 | invalid Stage-5 evidence | D at GATE |
| A16 | valid Stage-6 pass | terminal A |
| A17 | valid Stage-6 fail | terminal B |
| A18 | invalid/missing/truncated/controller-invalid Stage-6 evidence | D at EVAL |
| A19 | initial state | current stage PREFLIGHT; empty ledger; no terminal |
| A20 | out-of-order, wrong RUN_HEAD, or conflicting duplicate report | operational reject; state/terminal unchanged |
| A21 | interruption before StageOutcome atomic commit | no terminal; same stage retryable with same RUN_HEAD/parents |
| A22 | identical committed StageOutcome retried or terminal already committed | no science rerun; idempotent existing state; terminal immutable |
| A23 | deployable model input includes behavior/expert/target/hidden/future | D at TARGET |
| A24 | helper/finalizer disagrees with canonical advance, or retention fails after terminal | disagreement IMPLEMENTATION_BUG; retention operational; terminal unchanged |

A new semantic scenario not unambiguously covered here is a `CONTRACT_GAP` and
returns to Planner. An implementation bug already covered by these rules is fixed
without changing the contract. Repeated new cross-module semantic classes or
loss of one canonical authority is `ARCHITECTURE_ESCALATION` and stops incremental
patching.

## Verification Sequence

1. Planner contract only; no production code.
2. Maintainer execution-readiness review of exact contract head.
3. Test-only executable A01-A24 boundary.
4. Baseline boundary behavior against clean pre-implementation main where meaningful.
5. Maintainer exact-head `SPEC APPROVED` / `implementation_authorized=true`.
6. One bounded production implementation pass.
7. Run A01-A24, focused tests, full tests, compile/lint/format/mock/diff gates.
8. Maintainer reviews matrix and architecture as one unit.
9. Freeze exact implementation RUN_HEAD.
10. Run authoritative T075 stages from that clean head only.
11. Materialize exactly one terminal A/B/C/D and final retention manifest.
12. Planner exact-head scientific/architecture acceptance.
13. Maintainer exact-head implementation/operational acceptance and merge.

No scientific Stage 0-6 execution begins before step 9.

## Required PR Evidence

The final T075 pull request must report, at minimum:

1. recovery base, approved Planner contract commit, final implementation
   `RUN_HEAD`, and final merge head when applicable;
2. an explicit statement that PR #75 runtime artifacts were not used as
   authoritative recovery evidence;
3. the exact two frozen expected T065 source identities, both observed identities
   when obtainable, and the two ordered strict validation/source-check results;
4. raw candidate/group/owner counts, cross-split group count,
   excluded-non-owner count, and post-owner family/split availability;
5. selected 320-state family/split counts and the exact replay result;
6. every reached TARGET/TRAIN/GATE/EVAL metric and reached durable artifact
   identity;
7. for each substantial simulator stage: shard count, requested/actual worker
   count, exact ranges, completion counts, and wall-clock evidence;
8. local, focused, and full verification results plus any deviation and its
   disposition;
9. terminal case, terminal stage, `promotion`, `recommendation_code`, and exactly
   one planner-facing disposition consistent with the frozen Terminal Decision
   table above; Case C may explicitly be `close_v1_no_followup`;
10. final retention-manifest identity, retained artifact identities, retention
    owner/reason, downstream consumers, and deletion conditions;
11. every `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION`
    raised during recovery and its disposition.

This is a reporting/evidence contract only. It does not add scientific acceptance
criteria beyond the frozen experiment and A01-A24 semantics.

## Final Planner Review Checklist

Planner acceptance requires:

- only scientific change is global ownership before unchanged quotas;
- one canonical acceptance transition authority;
- git_commit and sha256 types never conflated;
- committed-outcome ledger and terminal_stage make retry/duplicate semantics exact;
- transaction computes final output identities before final StageOutcome identity;
- StageOutcome report write is the sole stage commit marker;
- TARGET failed barrier commits invalid outcome; interruption before commit remains retryable;
- ownership audit/selected states are same-stage sibling outputs, not parent/child commits;
- exact T065 expected source roles are `current_output`;
- SOURCE_REUSE begins from committed PREFLIGHT only; valid source identities become
  parents only after successful source checks, while A02 commits with PREFLIGHT-only
  parents and failed expected inputs represented in evidence;
- B/C are valid negative science; D is invalid experiment;
- Case C preserves T065's close-v1/no-promotion/Stage-6-skipped and at-most-one
  narrow diagnostic successor boundary;
- terminal promotion/recommendation fields match the frozen A/B/C/D decision table;
- logical Stage 3 is atomic TARGET barrier;
- lineage is explicit/minimal and contains no implicit external-parent mechanism;
- one exact RUN_HEAD owns authoritative execution;
- fixed 16-shard/16-worker protocol is followed and reported;
- command layer remains thin;
- PID/queue/process binding is non-semantic;
- no hidden/human-policy information enters deployable model;
- no frozen T065 science changes;
- no PR #75 runtime artifact becomes authoritative;
- required PR evidence is complete without becoming a second acceptance authority;
- no local semantic invention beyond this contract.

## Lifecycle

This recovery contract remains `DRAFT` until Main Maintainer posts exact-head
`SPEC APPROVED` / `implementation_authorized=true`.

That approval authorizes only bounded implementation against this contract. It
does not authorize redesign of T075 science or acceptance semantics.