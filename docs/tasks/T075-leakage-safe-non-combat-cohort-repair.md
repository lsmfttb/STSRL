# T075: Leakage-Safe Non-Combat Cohort Repair

## Architecture Recovery Declaration

This document is the single normative Planner contract for the T075 recovery line.
It supersedes the unmerged T075 specification/implementation history on PR #75 for
all future T075 implementation and acceptance decisions.

PR #75 remains only an architecture-failure audit record. Its task-specific
orchestration, recursive provenance/retention machinery, command-token matching,
duplicated validators, terminal helpers, PID/process proof, and runtime artifacts
are not accepted project state and must not be used as the T075 implementation
baseline or authoritative recovery evidence.

The recovery preserves the T075 scientific experiment while replacing the rejected
control plane with:

- one canonical acceptance state machine;
- one small `StageOutcomeCore` consumed by that state machine;
- stage-local scientific/fidelity classification separated from state transition;
- transactional stage-report commits;
- minimal explicit lineage;
- one frozen scientific `RUN_HEAD`;
- a bounded neutral command surface.

Architecture recovery base:

`bc9a6790f36ff036f90dc7f03ba0ff026a16788d`

Historical references:

- accepted T065 result: merged task T065;
- rejected T075 implementation/audit line: PR #75;
- previously approved T075 proposal: `e204c5d28cc0bee8013853e8680e8966f5c930a8`;
- contract-layer architecture escalation: PR #77 comment `5462214296`.

## Objective And Motivation

Repair the single cohort-partition defect exposed by T065 Case D and, only if the
repaired cohort is valid, continue the otherwise unchanged T065 learned non-combat
experiment.

T065 remains `DONE` with its valid Case D. T075 does not reinterpret, overwrite,
or weaken that result.

The only new scientific rule in T075 is:

> replay-equivalent candidates are assigned one deterministic global owner before
> the unchanged per-family/per-split quota selection.

Everything downstream of a valid selected cohort remains frozen T065 science
unless this document explicitly says otherwise.

## Baseline, Dependencies, And Frozen Upstream Identities

Current recovery baseline:

```text
RECOVERY_BASE = bc9a6790f36ff036f90dc7f03ba0ff026a16788d
T065_APPROVED_SPEC = a13c92a66b4d9ad9f6a730293cadc8d66b4a699c
STS_LIGHTSPEED_INTEGRATION = fee272f1ae21c283ad2161f55293cfe6d714134a
```

All values above are Git commit identities, not SHA-256 content digests.

T075 depends on:

- T033 public-context model-input encoder contract;
- T040 `expert_non_combat_v1`;
- T061 reachability-bottleneck evidence;
- T064 simulator-generated later-act curriculum result;
- T065 learned non-combat workflow, strict readers, retained Stage-1 evidence, and
  valid Case-D result;
- T071 simplified experiment execution/reuse convention;
- T074 core decision/policy boundary repair.

T034, T063, and T066 remain outside T075.

The authoritative task index contains the proposed `T075 | DRAFT` row on PR #77.
No implementation is authorized until the Main Maintainer publishes exact-head
`SPEC APPROVED` with `implementation_authorized=true`.

## Information-Regime Boundary

T075 remains inside the repository's simulator-generated training paradigm:

- no human trajectories or human action labels;
- no expert-policy imitation target;
- no hidden/future feature in the deployable non-combat model input;
- `expert_non_combat_v1` is a frozen bootstrap/continuation controller, not
  ground-truth supervision;
- selected states, counterfactual targets, model training, and evaluation are
  simulator generated.

Any change to public model input, replay identity, continuation policy, target
definition, model topology, training hyperparameters, Stage-5/Stage-6 gates, or
terminal scientific meaning is a `CONTRACT_GAP`, not implementation freedom.

## Scope And Explicit Non-Scope

In scope:

1. validate and reuse the two exact retained T065 source artifacts;
2. apply global replay-group ownership before unchanged quotas;
3. replay-verify the repaired 320-state cohort;
4. run the unchanged T065 target, training, Stage-5, and conditional Stage-6
   workflow if preceding stages are valid;
5. materialize one terminal A/B/C/D decision and final retention manifest;
6. implement only the small acceptance-core/state-transition layer and thin stage
   classification/adapters required by this contract.

Explicitly out of scope:

- recollecting Stage-1 sources;
- changing source scale, split assignment, replay key, quotas, or target-aware
  selection;
- new learned-policy architectures, reward definitions, action spaces, or
  hyperparameter sweeps;
- natural-A20 or live-game promotion claims;
- generic workflow frameworks;
- task-numbered production packages;
- recursive provenance discovery or proof graphs;
- per-stage retention manifests;
- exact shell-command-token identity;
- PID, queue, worker-process identity, or process-binding as scientific evidence;
- PR #75 runtime artifacts as authoritative evidence.

## Frozen Runtime And Checkout

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

Every authoritative stage command runs from `CODE` with:

```bash
cd "$CODE"
export PYTHONPATH="$NATIVE:$CODE/src"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$RUN_HEAD"
```

`RUN_HEAD` is frozen only after bounded implementation and the implementation-
independent A01-A24 suite pass. No authoritative Stage 0-6 scientific execution
begins before that point.

Wrong branch, dirty checkout, absent/wrong `RUN_HEAD`, malformed CLI invocation, or
an arbitrary wrong path rejected before a legitimate stage begins is an
operational invocation failure. It commits no stage report and creates no A/B/C/D
result.

If production code changes after authoritative scientific execution starts, the
old RUN_HEAD is retired. The Maintainer identifies the earliest semantically
affected stage, reruns acceptance, freezes a new RUN_HEAD, and reruns that stage
plus downstream stages.

## Frozen T065 Source Inputs

T075 reuses exactly these two retained T065 source files and never recollects them:

| Arm | role | Relative path | Bytes | SHA-256 |
|---|---|---|---:|---|
| stochastic | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| expert | `current_output` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

A valid source must pass the current strict T065 source reader and match:

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

Missing, unreadable, identity-invalid, strict-reader-invalid, or metadata-invalid
source input is a committed invalid SOURCE_REUSE result, not an invocation error.
No alias, basename search, manifest discovery, replacement, or alternate source is
allowed.

## Frozen Source, Split, And Cohort Constants

- player: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- source seeds: `650001..650256`;
- source driver seed: `654001`;
- source arms: stochastic and expert;
- battle controller: `oracle_search_v1_highest_mean_s20`.

Seed-derived splits:

- train: `650001..650154`;
- validation: `650155..650205`;
- heldout: `650206..650256`.

Canonical family order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas:

- train: 48;
- validation: 16;
- heldout: 16.

A valid repaired cohort contains exactly 320 selected states. Simulator seeds may
never change split.

## Public Model Input

Use `non-combat-model-input-v1` exactly:

- tactical snapshot dimension: 4634;
- public context dimension: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- no behavior/expert/target/outcome/hidden/future feature;
- training-split-only CPU float32 population normalization;
- population standard deviation clamped to at least 1.0 and checkpointed.

## Scientific Primitive: Global Replay Ownership

Selectable candidates must:

- pass the strict `t065-source-state-v1` reader;
- come from a problem-free terminal source run;
- belong to a mandatory family;
- retain the split implied by simulator seed;
- retain source provenance;
- pass existing T065 public/model/action/replay-input validation.

Malformed/provenance-invalid selectable rows fail closed at SELECTION_REPLAY. They
use `SOURCE_REUSE_FIDELITY` only when the defect is source-file-level; otherwise a
row-level defect that prevents candidate admission makes SELECTION_REPLAY invalid
under `SELECTION_OWNER_QUOTA_SHORTAGE` if the resulting frozen owner bucket misses
quota, or returns as a `CONTRACT_GAP` if it exposes a distinct acceptance meaning.
No additional selection failure taxonomy is created locally.

Replay equivalence is unchanged:

```text
(family, public_state_identity, ordered_legal_action_identities)
```

Canonical candidate JSON uses UTF-8, sorted keys, compact separators,
`ensure_ascii=False`, and `allow_nan=False`.

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

Selection algorithm:

1. admit all selectable candidates from both frozen source arms and all splits;
2. group globally by replay equivalence;
3. sort each group by complete `member_order_key`;
4. if distinct source rows have identical complete member-order keys, selection is
   invalid; no extra tie breaker is allowed;
5. otherwise the first member is the sole owner;
6. exclude all non-owners before quota selection;
7. keep the owner's seed-derived split;
8. within each `(family, split)` owner bucket, sort by the same member order and
   take exactly 48/16/16.

If any owner bucket is below quota, selection is invalid. There is no recollection,
scale increase, split reassignment, balancing, manual replacement, target-aware
selection, or replay-key change.

A valid selected cohort has exact quotas, unique selected replay keys, zero cross-
split replay overlap, exact replay of every selected public/model state and
ordered legal actions, and zero replacement after replay failure.

## Unchanged T065 Downstream Science

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
hidden/future resampling.

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
- `torch.manual_seed(model_seed)` before model construction;
- default `nn.Linear` initialization;
- Huber delta 1;
- Adam lr `1e-3` with frozen T065 defaults;
- exactly 1500 optimizer steps;
- minibatch 64 sampled with replacement by the frozen generator;
- gradient clip 10;
- `torch_threads=1`;
- no early stopping, architecture sweep, or checkpoint averaging;
- validation q_floor MAE selects checkpoint;
- exact MAE tie selects lower model seed.

### Stage-5 Gate

Use 64 heldout states. A complete valid Stage-5 classification passes iff all hold:

1. aggregate mean paired `q_floor(model)-q_floor(expert) > 0`;
2. median paired delta `>= 0`;
3. at least 3/4 family means `>= 0`;
4. 10,000-stratified-bootstrap `p_positive >= 0.90` using
   `random.Random(655001)`;
5. non-selected model-seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violation.

A complete valid failure is Case C. Invalid/incomplete Stage-5 evidence is Case D.

### Stage-6 Gate

Run only after complete valid Stage-5 pass.

- fresh seeds `651001..651256`;
- driver/fallback seed `654002`;
- arm order: stochastic, expert, learned-with-expert-fallback;
- 16 fixed shards x 16 seeds per arm;
- 768 valid terminal runs required for complete valid evidence;
- bootstrap 10,000 matched-seed resamples with `random.Random(655002)`;
- coverage `L/D >= 0.60`, `F/M <= 0.01`, `D != 0`, `M != 0` using unchanged T065
  D/L/M/F definitions.

A complete valid Stage-6 classification passes iff all hold:

1. matched mean terminal-floor delta `> 0`;
2. bootstrap `p_positive >= 0.80`;
3. learned Act-2 entry count `>=` expert;
4. zero controller errors and unreported truncations;
5. coverage passes;
6. stronger signal: learned Act-2 count `>` expert OR `p_positive >= 0.95`.

Complete valid pass -> A. Complete valid fail -> B. Invalid/incomplete evidence -> D.

## Canonical Types

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
StageFailureCode = PREFLIGHT_FIDELITY | SOURCE_REUSE_FIDELITY | SELECTION_MEMBER_ORDER_TIE | SELECTION_OWNER_QUOTA_SHORTAGE | SELECTION_DUPLICATE_OR_OVERLAP | SELECTION_REPLAY_MISMATCH | TARGET_STAGE3_VALIDATION | TRAIN_FIDELITY | GATE_EVIDENCE_INVALID | EVAL_EVIDENCE_INVALID
```

`RUN_HEAD`, `RECOVERY_BASE`, `T065_APPROVED_SPEC`, and
`STS_LIGHTSPEED_INTEGRATION` are `git_commit`. Artifact/content hashes, selection
digests, replay-group digests, and core digests are `sha256`.

## Artifact Identity

`ArtifactIdentity` serializes exactly as:

```json
{"role":"string","path":"string","sha256":"<64hex>","size_bytes":0}
```

Rules:

- `role` is a non-empty frozen role string;
- `path` is repository-relative POSIX under `artifacts/`;
- normalize backslashes to `/`, remove `.` components and one leading `./`;
- reject `..`;
- comparison is case-sensitive;
- basename-only matching is forbidden;
- `size_bytes` is `nonneg_int`;
- equality compares all four fields.

Frozen roles:

```text
current_output
preflight_report
source_reuse_report
ownership_audit
selected_states
selection_report
target_table
target_validation_report
checkpoint
training_report
gate_report
eval_report
terminal_report
retention_manifest
```

## Acceptance Architecture

The architecture deliberately separates stage scientific/fidelity classification
from workflow state transition.

```text
raw stage result
    -> frozen stage-specific validation/classification
    -> StageReport(StageOutcomeCore + evidence)
    -> compute prospective StageReport ArtifactIdentity
    -> advance(state, StageOutcomeCore, report_identity)
```

The prospective `report_identity` is commit metadata derived from final report
bytes; it is not scientific evidence and `advance()` never inspects evidence.

Stage validators may classify only their own stage result as:

- complete valid pass;
- complete valid negative result for GATE/EVAL;
- invalid/incomplete result with a frozen `StageFailureCode`.

Stage validators do not own stage ordering, retry, duplicate handling, terminal
selection, or lineage state transitions.

`advance()` is the only workflow/transition authority. It does not inspect
scientific metric fields, counts, predicates, or arbitrary evidence to infer
validity.

## StageOutcomeCore

The canonical semantic core is:

```text
StageOutcomeCore =
  task_id = T075
  run_head: git_commit
  stage: Stage
  valid: bool
  passed: bool
  parents: tuple[ArtifactIdentity]
  outputs: tuple[ArtifactIdentity]
  failure_code: StageFailureCode | null
  problems: tuple[string]
```

Its exact canonical JSON object contains only these keys:

```text
task_id
run_head
stage
valid
passed
parents
outputs
failure_code
problems
```

`parents`, `outputs`, and `problems` serialize as JSON arrays in their frozen order.
`failure_code` serializes as JSON null only for valid cores. Canonical JSON settings
are defined below.

Core invariants:

- `valid=true` -> `failure_code=null`;
- `valid=false` -> `passed=false`, `failure_code!=null`, `problems` non-empty;
- valid GATE/EVAL may have `passed=false` and remain valid negative science;
- PREFLIGHT/SOURCE_REUSE/SELECTION_REPLAY/TARGET/TRAIN with `valid=true` require
  `passed=true`;
- invalid stage -> no successful data output is promoted and `outputs=[]`;
- a frozen external source may appear as a successful SOURCE_REUSE parent but is
  never a stage output;
- `advance()` validates only core fields, canonical parent/output rules, legal
  transition, RUN_HEAD, duplicate/retry semantics, terminal semantics, and the
  supplied prospective report identity.

`core_digest(core)` is SHA-256 over canonical JSON serialization of the exact core
object above. Evidence bytes do not alter core semantics.

## AcceptanceState And Committed Ledger

```text
CommittedOutcome =
  stage: Stage
  core_digest: sha256
  report_identity: ArtifactIdentity

AcceptanceState =
  run_head: git_commit
  committed_outcomes: ordered tuple[CommittedOutcome]
  current_stage: Stage | None
  terminal_case: TerminalCase | None
  terminal_stage: Stage | None
```

Initial state:

```text
run_head = RUN_HEAD
committed_outcomes = ()
current_stage = PREFLIGHT
terminal_case = None
terminal_stage = None
```

Durable state is reconstructed only by reading committed stage reports in canonical
stage order, extracting their cores, computing each core digest and report
ArtifactIdentity, and replaying them through the same `advance` authority. There is
no mutable workflow-state file and no second transition authority.

## Legal Transitions

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

Poor learned-policy performance alone produces B or C, never D.

## Transition Precedence And Retry Semantics

The single transition signature is conceptually:

```text
advance(state: AcceptanceState,
        core: StageOutcomeCore,
        report_identity: ArtifactIdentity) -> AcceptanceState
```

`report_identity` must use the frozen report role/path for `core.stage` and the
SHA-256/size of the exact final StageReport bytes that are proposed for atomic
commit.

For a candidate core/report identity, `advance` applies exactly:

1. reject if `core.run_head != state.run_head`;
2. compute `core_digest(core)`;
3. if the ledger already contains `core.stage`, handle duplicate before terminal
   or current-stage checks:
   - identical core digest and identical committed report identity -> idempotent
     existing state;
   - identical core digest but different report identity -> operational evidence/
     persistence conflict; state unchanged and existing report is not overwritten;
   - different core digest -> operational conflicting duplicate; state unchanged;
4. if terminal already exists, reject any new uncommitted stage; state unchanged;
5. require `core.stage == state.current_stage`;
6. require the exact legal `(valid, passed, failure_code)` combination;
7. require `report_identity` role/path to equal the frozen report role/path for the
   stage;
8. validate the frozen parent/output shape for that stage/result class;
9. apply the transition table and append
   `CommittedOutcome(stage, core_digest, report_identity)`;
10. if terminal, set `terminal_case`, `terminal_stage`, `current_stage=None`;
    otherwise advance to the next stage.

Out-of-order stage, wrong RUN_HEAD, report-role/path mismatch, or conflicting
duplicate is an operational rejection, not Case D.

An already committed identical core/report identity is never re-executed for
science. The caller returns/validates the existing committed report.

## Canonical Parent And Output Rules

Normal parents must resolve, in exact frozen order, to report/output identities from
previously committed T075 reports.

SOURCE_REUSE is the only closed-world external-input exception:

- before SOURCE_REUSE work begins, only the committed PREFLIGHT report must be
  validated;
- the two T065 source literals are frozen expected external inputs;
- on valid SOURCE_REUSE, both sources must have exact observed identity equality
  plus strict-reader and metadata success, and core parents are exactly
  `[PREFLIGHT report, stochastic source, expert source]`;
- on invalid SOURCE_REUSE, core parents are exactly `[PREFLIGHT report]`; failed
  source expectations remain evidence only;
- no other external parent mechanism exists.

Other frozen parent/output shapes:

| Stage/result | parents | outputs |
|---|---|---|
| PREFLIGHT valid/invalid | `[]` | `[]` |
| SOURCE_REUSE valid | PREFLIGHT + two validated frozen sources | `[]` |
| SOURCE_REUSE invalid | PREFLIGHT | `[]` |
| SELECTION_REPLAY valid | PREFLIGHT + SOURCE_REUSE report | ownership audit + selected states |
| SELECTION_REPLAY invalid | PREFLIGHT + SOURCE_REUSE report | `[]` |
| TARGET valid | PREFLIGHT + SELECTION_REPLAY report + selected states | target table |
| TARGET invalid | same committed parents as valid TARGET | `[]` |
| TRAIN valid | TARGET report + target table | two checkpoints ordered 653001,653002 |
| TRAIN invalid | TARGET report + target table | `[]` |
| GATE valid/invalid | TRAIN report + selected checkpoint + target table | `[]` |
| EVAL valid/invalid | valid-pass GATE report + selected checkpoint | `[]` |

Ownership audit and selected states are same-stage sibling outputs of one valid
SELECTION_REPLAY transaction. Neither is a committed parent of the other.

The GATE/EVAL stage classifier, not `advance`, validates that the selected checkpoint
parent is the checkpoint selected by the frozen TRAIN rule. `advance` checks only
that the checkpoint identity is one of the committed TRAIN checkpoint outputs and
that all other parent identities/order match the frozen lineage. This keeps model-
selection science out of workflow transition logic.

## StageReport And Canonical JSON

Every persisted T075 stage report contains the core plus evidence with exact
top-level keys:

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
failure_code: StageFailureCode | null
problems: [string]
evidence: Evidence
```

The top-level semantic fields from `task_id` through `problems` serialize the exact
`StageOutcomeCore` object used for `core_digest`.

All T075 control/report JSON uses UTF-8 canonical JSON:

```text
sort_keys=True
separators=(',', ':')
ensure_ascii=False
allow_nan=False
one trailing newline
```

Unknown top-level keys in v1 T075 reports are rejected. Existing unchanged T065
scientific payloads keep their already-merged strict schemas.

Frozen report mapping:

| Stage | Path | role | schema_id |
|---|---|---|---|
| PREFLIGHT | `stage0-preflight.json` | `preflight_report` | `t075-preflight-report-v1` |
| SOURCE_REUSE | `stage0-source-reuse.json` | `source_reuse_report` | `t075-source-reuse-report-v1` |
| SELECTION_REPLAY | `stage1-selection-report.json` | `selection_report` | `t075-selection-report-v1` |
| TARGET | `stage2-validation.json` | `target_validation_report` | `t075-target-validation-report-v1` |
| TRAIN | `stage4-training-report.json` | `training_report` | `t075-training-report-v1` |
| GATE | `stage5-heldout-report.json` | `gate_report` | `t075-stage5-report-v1` |
| EVAL | `stage6-complete-run-report.json` | `eval_report` | `t075-stage6-report-v1` |

## Evidence Model

Evidence is stage-classification evidence, not workflow state. `advance()` never
parses it.

For all stages except SOURCE_REUSE:

```text
Evidence = CompleteEvidence | InvalidEvidence

CompleteEvidence =
  kind = complete
  <stage-specific complete fields>

InvalidEvidence =
  kind = invalid
  failed_check: string
  completed_checks: tuple[CheckRecord]
  observed_counts: map[string, nonneg_int]
  wall_clock_seconds: number

CheckRecord =
  name: string
  status: passed | failed
  counts: map[string, nonneg_int]
  problems: tuple[string]
```

Invalid-evidence rules:

- `failed_check` must be one of the frozen check names for that stage;
- `completed_checks` is exactly the deterministic checked prefix through the first
  failing check;
- all records before the final record have `status=passed`;
- the final record name equals `failed_check` and has `status=failed`;
- `observed_counts` contains only counts actually known at failure time;
- absent scientific metrics are absent, not fake zero, NaN, null, or success
  placeholders;
- `wall_clock_seconds` is finite and nonnegative;
- `InvalidEvidence` is permitted only with `core.valid=false` and the stage's
  frozen failure code;
- finer internal diagnostics may exist outside the normative evidence object but
  do not create new acceptance semantics.

For valid stages, complete evidence is required. For complete valid GATE/EVAL,
scientific metrics may yield `passed=false` while `valid=true`.

## Frozen Stage Classification Boundaries

### PREFLIGHT

Frozen ordered checks:

1. `runtime_imports`
2. `simulator_identity`
3. `checkpoint_roundtrip`
4. `frozen_controller_action_space`
5. `model_input_schema_dimensions`
6. `public_input_firewall_capability`
7. `torch_runtime`

Any failed check -> invalid core with `PREFLIGHT_FIDELITY`.

Complete evidence must record all seven passed checks and the frozen recovery base,
T065 spec commit, sts_lightspeed integration commit, simulator identity, and model-
input schema identity.

### SOURCE_REUSE

SOURCE_REUSE uses one stage-specific evidence form for both valid and invalid
classification because the external input identities themselves are the audited
failure surface.

```text
SourceReuseEvidence =
  kind = source_reuse
  sources: exactly two SourceRecord values, stochastic then expert
  validation_passed: bool

SourceRecord =
  arm: stochastic_non_combat_v1 | expert_non_combat_v1
  expected_artifact: ArtifactIdentity
  observed_artifact: ArtifactIdentity | null
  strict_reader_passed: bool
  metadata_passed: bool
  failure_class: none | missing | unreadable | identity_mismatch | strict_reader_invalid | metadata_invalid
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
`observed_artifact=null` is allowed only when no readable artifact identity can be
obtained. Metadata is populated when derivable and otherwise null. A passing
record has complete metadata and no null required values.

Failure precedence:

1. `missing`
2. `unreadable`
3. `identity_mismatch`
4. `strict_reader_invalid`
5. `metadata_invalid`
6. `none`

If a later validation phase is not reached, its total boolean is `false`; the
failure class identifies the first failed phase.

Both records pass -> complete valid SOURCE_REUSE core, `failure_code=null`, parents
include both validated sources. Any record fails -> invalid core,
`SOURCE_REUSE_FIDELITY`, parents `[PREFLIGHT]`, problems non-empty.

### SELECTION_REPLAY

Frozen ordered classifier checks:

1. `candidate_domain`
2. `member_order_uniqueness`
3. `owner_quota_availability`
4. `selected_uniqueness`
5. `selected_cross_split_overlap`
6. `selected_replay`

Failure mapping:

- `member_order_uniqueness` -> `SELECTION_MEMBER_ORDER_TIE`;
- `owner_quota_availability` -> `SELECTION_OWNER_QUOTA_SHORTAGE`;
- `selected_uniqueness` or `selected_cross_split_overlap` ->
  `SELECTION_DUPLICATE_OR_OVERLAP`;
- `selected_replay` -> `SELECTION_REPLAY_MISMATCH`.

`candidate_domain` is a prerequisite admission check rather than a separate new
acceptance category. Malformed/provenance-invalid rows are excluded exactly under
the frozen selectable-candidate rule. If that leaves an owner bucket below quota,
`owner_quota_availability` fails with `SELECTION_OWNER_QUOTA_SHORTAGE`. If a
candidate-domain defect exposes a meaning not reducible to the frozen source
fidelity or quota semantics, classification stops as `CONTRACT_GAP`; the
Implementer must not invent a new failure code.

Complete valid evidence requires:

- post-owner family/split availability;
- `selected_count=320`;
- exact selected family/split quotas;
- selected replay identity digests;
- replay `shard_count=16`;
- replay requested/actual workers `16/16`;
- exact 16 ranges over state indices 0..319;
- `attempted=320`, `restored=320`;
- mismatch/replacement/duplicate/cross-split-overlap counts all zero;
- wall-clock evidence.

Ownership audit path/role/schema:

```text
stage1-ownership-audit.json
role = ownership_audit
schema = t075-ownership-audit-v1
```

It records candidate/group/owner counts, cross-split group count, excluded non-owner
count, post-owner availability, group-size histogram, and groups/members ordered by
the frozen ownership rules. It is a valid-stage data output, not a separate
StageOutcome.

Selected-state output is `stage1-selected-states.jsonl`, role `selected_states`,
with exactly one complete strict current `t065-source-state-v1` object per line,
indices 0..319, and final newline.

For invalid SELECTION_REPLAY, neither ownership audit nor selected states is a
successful promoted output; core outputs are empty. Available diagnostic counts
belong only in `InvalidEvidence.observed_counts`.

### TARGET / Logical Stage-3 Barrier

Logical Stage 3 is inside TARGET, not a separate workflow stage.

Frozen check order:

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

Any failed check -> invalid TARGET core with `TARGET_STAGE3_VALIDATION`; no target
table is promoted. The invalid evidence records the deterministic check prefix
through the failing check.

Complete valid evidence requires all ten checks passed, selected-state count 320,
complete target/action counts, exact family/split counts, continuation replication,
16 shards/workers with exact ranges, zero violations, and wall-clock evidence.

The valid target table is `stage2-target-table.json`, role `target_table`, using the
unchanged strict T065 schema `t065-counterfactual-target-table-v1` version 1.

### TRAIN

Frozen ordered classifier checks:

1. `strict_target_table`
2. `training_config`
3. `normalizer`
4. `model_seed_runs`
5. `checkpoint_selection`

Any failure -> invalid TRAIN core with `TRAIN_FIDELITY`, no checkpoint output, and
no requirement for selected model seed/checkpoint in evidence.

Complete valid evidence requires:

- model seeds exactly `[653001,653002]`;
- frozen T065 training configuration;
- training-split normalizer provenance;
- finite validation MAE for each seed;
- two checkpoint identities ordered 653001 then 653002;
- selected model seed/checkpoint by frozen validation-MAE rule;
- wall-clock evidence.

Checkpoint payloads retain the unchanged strict T065 checkpoint schema.

### GATE

Frozen ordered classifier checks for evidence validity:

1. `heldout_table`
2. `selected_checkpoint`
3. `paired_delta_completeness`
4. `finite_metrics`
5. `public_input_firewall`

Failure of any check -> invalid GATE core with `GATE_EVIDENCE_INVALID`.

Complete valid evidence requires all data needed for the six frozen Stage-5
scientific predicates: 64 heldout states, selected/non-selected model seed,
aggregate mean, median, four family means, bootstrap `p_positive`, non-selected
mean, zero violation counts, predicate results, and wall-clock evidence.

Only after complete evidence passes the five evidence-validity checks are the six
scientific predicates applied. All six true -> valid+pass -> EVAL. Any scientific
predicate false with evidence otherwise complete -> valid+fail -> Case C.

### EVAL

Frozen ordered classifier checks for evidence validity:

1. `required_run_slots`
2. `terminal_run_completeness`
3. `controller_integrity`
4. `truncation_integrity`
5. `coverage_denominators`
6. `finite_metrics`

Failure of any check -> invalid EVAL core with `EVAL_EVIDENCE_INVALID`.

For invalid EVAL, actual attempted/completed/terminal/error/truncation counts belong
in `InvalidEvidence.observed_counts`. `terminal_run_count=768` is never asserted for
invalid evidence.

Complete valid evidence requires:

- fresh seed range 651001..651256;
- arm order stochastic/expert/learned;
- requested and valid terminal run count exactly 768;
- 16 shards per arm;
- requested/actual worker count 16 per active arm batch;
- exact seed ranges and wall-clock evidence;
- valid coverage D/L/M/F and ratios;
- finite mean terminal-floor delta and bootstrap probability;
- learned/expert Act-2 entry counts;
- controller error count 0;
- truncation count 0;
- six Stage-6 scientific predicate results.

Only after evidence is complete/valid are the six Stage-6 scientific predicates
applied. All true -> valid+pass -> A. Otherwise complete valid evidence ->
valid+fail -> B.

## Transactional Stage Commit

For a legitimately reached stage:

1. validate checkout, RUN_HEAD, canonical state, and already-committed parents
   required to begin the stage;
2. write expensive/intermediate prospective data under `ROOT/.tmp/`;
3. run the frozen stage classifier;
4. construct final core:
   - complete valid result uses `valid=true` and frozen pass semantics;
   - invalid/incomplete result uses `valid=false`, `passed=false`, the stage's
     frozen failure code, empty successful outputs, and non-empty problems;
5. for a complete valid stage, atomically promote validated data outputs to frozen
   final paths and compute their final ArtifactIdentity values before finalizing
   the core;
6. construct the final StageReport from core + evidence and canonical-serialize it;
7. compute the prospective StageReport ArtifactIdentity from its exact final bytes,
   frozen role, and frozen path;
8. call the single canonical `advance(state, core, prospective_report_identity)`;
   this is a pure prospective check and creates no durable state;
9. atomically write exactly those final StageReport bytes to the frozen report path;
   this write is the sole stage commit marker;
10. after successful report write, durable state is the state already determined by
    the same `advance` call and may be reconstructed from committed reports;
11. if terminal, materialize the case-constrained terminal report from canonical
    state and the frozen terminal decision table.

There is no provisional core identity, provisional report identity, or second
transition path.

If data promotion succeeds but stage-report commit is interrupted, those data files
are uncommitted and ignored as parents; retry may deterministically overwrite them.
No terminal result exists.

If invalid classification completes but stage-report write is interrupted, the
stage remains uncommitted and retryable. Once an invalid report commits, it is
immutable fidelity evidence and is not rerun for a better result.

## Terminal Decision

Single path/role/schema:

```text
terminal-decision-report.json
role = terminal_report
schema = t075-terminal-decision-report-v1
```

Exact semantic fields:

```text
task_id = T075
run_head: git_commit
terminal_case: A | B | C | D
terminal_stage: Stage
reached_stages: [Stage]
skipped_stages: [Stage]
stage_report_identities: [ArtifactIdentity]
promotion: Promotion
recommendation_code: RecommendationCode
recommendation: string
problems: [string]
```

Reached stages are the canonical prefix through terminal stage. Skipped stages are
the remaining suffix. Stage report identities follow reached-stage order.

Terminal mapping:

- A / EVAL: `promotion=experimental_public_with_expert_fallback`,
  `recommendation_code=review_joint_policy_next_step`; disposition is to review
  T066 or one narrower joint-policy task. No natural-A20/live-game claim.
- B / EVAL: `promotion=no_promotion`,
  `recommendation_code=narrow_transfer_followup`; one narrow follow-up may be
  selected from observed screen coverage, target-horizon/rollout-policy mismatch,
  or run-distribution shift. Do not authorize a larger natural run merely because
  the 256 fresh seeds are neutral.
- C / GATE: `promotion=no_promotion`; EVAL/Stage 6 is skipped and v1 closes.
  `recommendation_code` is exactly one of:
  - `close_v1_no_followup`;
  - `narrow_target_model_diagnostic`.
  There is at most one narrow diagnostic successor.
- D / first invalid reached stage: `promotion=no_promotion`,
  `recommendation_code=rerun_same_experiment_after_narrow_repair`; no policy
  conclusion is allowed; exactly one narrow repair needed to rerun the same frozen
  experiment is reported; downstream scientific stages are skipped.

Every terminal report carries exactly one Planner-facing disposition. The
`recommendation` string describes the selected disposition and is not a second
decision authority.

The first terminal state implied by committed cores is immutable. If terminal-file
materialization is interrupted after the terminal stage report committed, restart
reconstructs the same state and materializes a terminal report constrained to the
same case/table. A conflicting terminal case/stage/promotion outside the frozen
mapping is an operational integrity failure and cannot reinterpret science.

## Final Retention

Path/role/schema:

```text
t075-retention-manifest.json
role = retention_manifest
schema = t075-retention-manifest-v1
```

Required semantic fields:

```text
task_id = T075
run_head: git_commit
terminal_case: A | B | C | D
retention_owner = T075
retention_reason: string
terminal_report_identity: ArtifactIdentity
reused_artifacts: [ArtifactIdentity]
produced_artifacts: [ArtifactIdentity]
downstream_consumers: [string]
deletion_condition: [string]
problems: [string]
```

Reused artifacts are exactly the two T065 source identities in stochastic/expert
order. Produced artifacts include committed reached-stage reports and valid durable
data outputs in canonical stage order, then role/path order. No recursive discovery.

T075 owns produced outputs from first committed stage until terminal/retention
result is merged or the task is formally abandoned. It only holds, and does not
own/delete/rewrite, the T065 sources.

T065 source hold is released after terminal+manifest merge or formal T075 closure,
no approved/open consumer remains, and no Maintainer reproduction hold remains.
T075 large payloads/checkpoints may be deleted after terminal merge when compact
reports/retention manifest remain, no approved downstream consumer remains, and no
reproduction hold remains. Historical recorded identities are never rewritten.

Retention failure after terminal is operational; it does not change A/B/C/D.

## Frozen Durable Output Surface

Under `artifacts/t075-leakage-safe-non-combat-cohort-repair/`:

```text
stage0-preflight.json
stage0-source-reuse.json
stage1-ownership-audit.json           # valid SELECTION_REPLAY only
stage1-selected-states.jsonl          # valid SELECTION_REPLAY only
stage1-selection-report.json
stage2-target-table.json              # valid TARGET only
stage2-validation.json
stage4-checkpoints/                   # valid TRAIN only
stage4-training-report.json
stage5-heldout-report.json
stage6-complete-run-report.json       # only if EVAL reached
terminal-decision-report.json
t075-retention-manifest.json
```

Temporary data belongs under `ROOT/.tmp/` and is never a canonical parent.

## Frozen Shard And Worker Plan

Authoritative substantial execution uses the repository's 16-logical-core resource
assumption.

SELECTION_REPLAY replay and TARGET each use exactly 16 contiguous 20-state shards:

```text
00 000..019   04 080..099   08 160..179   12 240..259
01 020..039   05 100..119   09 180..199   13 260..279
02 040..059   06 120..139   10 200..219   14 280..299
03 060..079   07 140..159   11 220..239   15 300..319
```

Requested and actual worker count for an authoritative valid run: 16.

EVAL uses, per arm, 16 contiguous 16-seed shards over 651001..651256:

```text
start(i) = 651001 + 16*i
end(i)   = 651016 + 16*i
```

Arm order: stochastic, expert, learned. Requested/actual worker count per active arm
batch: 16; at most 16 concurrent simulator workers.

If the host cannot establish the required worker plan before substantial stage
work, the stage does not start and commits no StageReport. This is operationally
incomplete, not Case D. No silent worker downgrade.

For each substantial simulator stage, evidence/PR reporting records shard count,
requested/actual worker count, exact ranges, completion counts, and wall-clock.
PID/queue/process identity is non-semantic.

## Reproduction Commands

The recovery extends neutral `sts_combat_rl.commands.non_combat_learning`. No T075-
numbered production package or generic workflow framework is permitted.

Reference commands freeze semantic arguments and paths; literal shell-token/string
identity is not an acceptance criterion.

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

No T075 source-collection command exists.

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

Finalization validates/materializes existing canonical terminal state and retention;
it never recomputes A/B/C/D.

## Required Verification

All Python gates use the pinned interpreter:

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

If pinned `$PY` lacks a required module, readiness fails; do not silently substitute
another interpreter.

## Allowed Implementation Freedom

Allowed:

- concrete Python class/function names implementing the frozen core/types;
- atomic-write helper details consistent with transactional semantics;
- multiprocessing/process-pool implementation;
- temporary filenames under the uncommitted area;
- bounded reuse of neutral merged T065 helpers/readers/scientific payloads;
- finer stage-local diagnostics that do not create new acceptance meanings;
- `observed_counts` keys for actually available stage-local diagnostic counts,
  because `advance()` does not inspect those keys.

Forbidden:

- another workflow/transition authority;
- `advance()` inferring validity by reading scientific metrics/evidence;
- one success-shaped evidence schema forced onto invalid outcomes;
- parallel per-stage nullable failure schemas merely to satisfy serialization;
- task-specific command-token equality;
- PID/process binding as acceptance science;
- recursive retention/provenance discovery;
- per-stage retention manifests;
- task-numbered production package or generic workflow framework;
- PR #75 orchestration/runtime outputs as authoritative state;
- source recollection or scientific-constant changes;
- acceptance expected values generated by production helpers under test.

## Normative Acceptance Matrix

Before production implementation, the Maintainer translates A01-A24 into an
implementation-independent executable test boundary. Expected literals/fixtures
must not be generated by production code under test.

| ID | Scenario | Required result |
|---|---|---|
| A01 | exact frozen source identities/roles/metadata | valid SOURCE_REUSE; parents PREFLIGHT + two sources; failure code null |
| A02 | missing/unreadable/hash/size/role/strict-reader/metadata-invalid frozen source | invalid SOURCE_REUSE / `SOURCE_REUSE_FIDELITY` / parents PREFLIGHT only -> D |
| A03 | cross-split replay-equivalent raw candidates | deterministic global owner; not itself error |
| A04 | exact full member-order tie between distinct rows | invalid SELECTION_REPLAY / `SELECTION_MEMBER_ORDER_TIE` -> D |
| A05 | owner bucket below quota | invalid SELECTION_REPLAY / `SELECTION_OWNER_QUOTA_SHORTAGE` -> D |
| A06 | selected duplicate or cross-split replay overlap | invalid SELECTION_REPLAY / `SELECTION_DUPLICATE_OR_OVERLAP` -> D |
| A07 | all 320 selected states replay exactly under fixed 16x20/16-worker plan | valid SELECTION_REPLAY; 320 complete outputs |
| A08 | one selected replay mismatch | invalid SELECTION_REPLAY / `SELECTION_REPLAY_MISMATCH` -> D; no replacement |
| A09 | TARGET missing/duplicate/nonfinite/wrong legal-action order/continuation seed | invalid TARGET / `TARGET_STAGE3_VALIDATION`, failed check identifies frozen barrier check -> D |
| A10 | TARGET public-input firewall or committed lineage failure | invalid TARGET / `TARGET_STAGE3_VALIDATION` -> D; TRAIN forbidden |
| A11 | target/intermediate data exists but TARGET StageReport did not commit | TARGET incomplete; retry allowed; no terminal |
| A12 | valid TARGET then TRAIN classification | valid TRAIN -> GATE; completed TRAIN fidelity failure -> invalid TRAIN / `TRAIN_FIDELITY` -> D |
| A13 | complete valid Stage-5 evidence and all six scientific predicates pass | valid GATE pass -> EVAL |
| A14 | complete valid Stage-5 evidence but one or more scientific predicates fail | valid GATE fail -> C; EVAL absent; disposition closes v1 with zero or one narrow diagnostic |
| A15 | incomplete/invalid Stage-5 evidence | invalid GATE / `GATE_EVIDENCE_INVALID` -> D |
| A16 | complete valid Stage-6 evidence and all six scientific predicates pass | valid EVAL pass -> A |
| A17 | complete valid Stage-6 evidence but one or more scientific predicates fail | valid EVAL fail -> B |
| A18 | missing/incomplete/truncated/controller-invalid/nonfinite Stage-6 evidence | invalid EVAL / `EVAL_EVIDENCE_INVALID` -> D; no fake 768/metric placeholders |
| A19 | initial state | current stage PREFLIGHT; empty ledger; no terminal |
| A20 | out-of-order stage, wrong RUN_HEAD, or conflicting duplicate core/report | operational reject; state/terminal unchanged |
| A21 | interruption before StageReport atomic commit | no committed core/report; same stage retryable with same RUN_HEAD/parents |
| A22 | identical committed core+report identity retried, or terminal already committed | no science rerun; existing report/state returned; terminal immutable |
| A23 | deployable model input includes behavior/expert/target/hidden/future | invalid TARGET / `TARGET_STAGE3_VALIDATION` at `public_input_firewall` -> D |
| A24 | helper/finalizer disagrees with canonical advance, or retention fails after terminal | disagreement `IMPLEMENTATION_BUG`; retention failure operational; terminal unchanged |

No A25 is added for the evidence/core refactor. A new semantic scenario not
unambiguously covered by the frozen classifier/core mapping is a `CONTRACT_GAP`.
Repeated new cross-module semantic classes or loss of one canonical authority is
`ARCHITECTURE_ESCALATION`.

## Failure Attribution And Fail-Closed Rules

- B/C are complete valid negative science.
- D means invalid/incomplete experiment or frozen-fidelity failure.
- Operational invocation/resource failure before a stage starts creates no
  scientific terminal result.
- Invalid classification that successfully commits a report creates D at that
  stage and stops downstream scientific execution.
- A stage classifier may use only failure meanings frozen in `StageFailureCode`.
  If a real failure cannot be mapped without inventing a new semantic category,
  stop and report `CONTRACT_GAP`.
- A corrective pass followed by another new cross-module semantic class is an
  `ARCHITECTURE_ESCALATION` signal; do not resume field-by-field patching.

## Required Pull-Request Evidence

The final T075 PR must report at minimum:

1. recovery base, approved Planner contract commit, final implementation RUN_HEAD,
   and final merge head when applicable;
2. explicit statement that PR #75 runtime artifacts were not used as authoritative
   recovery evidence;
3. exact two retained T065 source identities and strict validation result;
4. candidate/group/owner counts, cross-split group count, excluded-non-owner count,
   and post-owner family/split availability;
5. selected 320-state family/split counts and exact replay result;
6. every reached TARGET/TRAIN/GATE/EVAL classification, failure code if invalid,
   scientific metrics when complete, and durable artifact identity;
7. for each substantial simulator stage: shard count, requested/actual workers,
   exact ranges, completion counts, and wall-clock;
8. local, focused, and full verification results plus any deviation/disposition;
9. terminal case, terminal stage, promotion, recommendation code, and exactly one
   Planner-facing disposition;
10. final retention-manifest identity, retained artifact identities, retention
    owner/reason, downstream consumers, and deletion conditions;
11. every `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION` raised
    during recovery and its disposition.

This is reporting/evidence scope only. It does not add scientific acceptance gates.

## Verification And Execution Sequence

1. Planner contract only; no production code.
2. Maintainer execution-readiness review of exact contract head.
3. Test-only executable A01-A24 boundary.
4. Baseline boundary behavior against clean pre-implementation main where meaningful.
5. Maintainer exact-head `SPEC APPROVED` / `implementation_authorized=true`.
6. One bounded implementation pass.
7. Run A01-A24, focused tests, full tests, compile/lint/format/mock/diff gates.
8. Maintainer reviews acceptance matrix and architecture as one unit.
9. Freeze exact implementation RUN_HEAD.
10. Run authoritative T075 scientific stages from that clean head only.
11. Materialize exactly one terminal A/B/C/D and final retention manifest.
12. Planner exact-head scientific/architectural acceptance.
13. Maintainer exact-head implementation/operational acceptance and merge.

No scientific Stage 0-6 execution begins before step 9.

## Final Planner Review Checklist

Planner semantic/architecture acceptance requires:

- only scientific change is global ownership before unchanged quotas;
- stage classification and workflow transition are separate layers;
- `advance()` consumes only `StageOutcomeCore` plus prospective report identity,
  never scientific evidence;
- one canonical `advance()` authority owns stage/terminal/retry semantics;
- fixed `StageFailureCode` meanings cover A01-A24 invalid outcomes without an open
  validator taxonomy;
- invalid evidence omits unavailable metrics rather than fabricating success-shaped
  placeholders;
- valid GATE/EVAL negative science remains C/B, distinct from invalid D;
- committed-outcome ledger/core+report identity makes A20/A22 duplicate semantics
  exact;
- StageReport write is the sole stage commit marker;
- TARGET failed barrier commits invalid outcome; interruption remains retryable;
- SOURCE_REUSE invalid path uses PREFLIGHT-only parents and expected-source evidence;
- ownership audit/selected states are same-stage sibling outputs;
- ArtifactIdentity lineage is explicit/minimal;
- one exact RUN_HEAD owns authoritative scientific execution;
- fixed worker/shard protocol is followed and reported;
- command layer remains thin;
- no human/hidden/future information enters deployable model;
- no frozen T065 science changes;
- Case C preserves T065's at-most-one diagnostic boundary;
- PR #75 runtime/control-plane artifacts remain non-authoritative;
- Required PR Evidence is complete without becoming a second acceptance authority;
- no recursive proof/retention/PID/command-token/generic-workflow ceremony returns;
- no downstream semantic invention is required to encode A01-A24.

## Lifecycle

This recovery contract remains `DRAFT` until Main Maintainer posts exact-head
`SPEC APPROVED` / `implementation_authorized=true`.

That approval authorizes only bounded implementation against this contract. It does
not authorize redesign of T075 science or acceptance semantics.
