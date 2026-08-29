# T075: Leakage-Safe Non-Combat Cohort Repair

## Architecture Recovery Declaration

This document is the single normative Planner contract for the T075 recovery line.
It supersedes the unmerged T075 specification/implementation history on PR #75 for
all future implementation and acceptance decisions.

PR #75 is retained only as an architecture-failure audit record. Its production
implementation, task-specific orchestration, validators, command-matching logic,
per-stage retention machinery, acceptance helpers, and runtime artifacts are not
accepted project state and must not be used as the recovery implementation
baseline.

The accepted scientific primitive from that line is the leakage-safe global
ownership rule described below. Useful implementation-independent test ideas and
truly generic execution primitives may be selectively salvaged only after they
are checked against this contract.

Architecture recovery base:

`bc9a6790f36ff036f90dc7f03ba0ff026a16788d`

Historical references:

- accepted T065 result: merged task T065;
- rejected T075 implementation/audit line: PR #75;
- previously approved T075 proposal: `e204c5d28cc0bee8013853e8680e8966f5c930a8`.

The recovery intentionally keeps the T075 scientific experiment but replaces the
control-plane architecture and removes nonessential execution/retention ceremony
that caused the failed implementation to grow far beyond the scientific change.

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

## Scientific And Information-Regime Boundary

T075 remains inside the repository training paradigm:

- no human trajectories or human action labels;
- no expert-policy imitation target;
- no hidden/future feature in the deployable non-combat model input;
- `expert_non_combat_v1` is a frozen bootstrap/continuation controller, not
  ground-truth supervision;
- selected states, counterfactual targets, model training, and evaluation are
  simulator generated;
- T034, T063, and T066 are outside this task.

Any implementation change that alters the public model input, replay identity,
continuation policy, target definition, model topology, training hyperparameters,
or Stage-5/Stage-6 scientific gates is a `CONTRACT_GAP`, not an implementation
fix.

## Frozen T065 Scientific Inputs

### Retained Stage-1 source evidence

T075 reuses exactly these two retained T065 raw source files and never recollects
them:

| Arm | Relative path | Bytes | SHA-256 |
|---|---|---:|---|
| `stochastic_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json` | 5,352,891,044 | `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61` |
| `expert_non_combat_v1` | `artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json` | 3,710,180,244 | `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c` |

The raw files must pass the current strict T065 source reader and match the
published T065 frozen configuration, simulator identity, source arm, driver seed,
seed range, controller provenance, terminal-run counts, shard plan, and action
space. Their exact file identity is sufficient input identity for T075 recovery;
the implementation must not rediscover them by recursively searching retention
manifests or historical aliases.

If an exact file is missing, unreadable, hash/size invalid, or fails strict T065
metadata validation, Stage `SOURCE_REUSE` is invalid and T075 ends Case D.

Source recollection, source replacement, alternate aliases, and automatic
best-effort discovery are forbidden.

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

Selectable families, in canonical order:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

Per-family quotas:

- train: 48;
- validation: 16;
- heldout: 16.

A valid cohort has exactly 320 selected states.

Other screens remain fallback-only and are not selectable training states.

### Public model input

Use `non-combat-model-input-v1` exactly:

- tactical snapshot dimension: 4634;
- public context dimension: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- no expert/behavior/target/outcome/hidden/future feature;
- training-split-only CPU float32 population normalization, with std clamped to
  at least 1.0 and then checkpointed unchanged.

## T075 Scientific Primitive: Global Ownership

Selectable candidates must:

- pass the strict `t065-source-state-v1` reader;
- come from a problem-free terminal source run;
- belong to a mandatory family;
- retain their simulator-seed-derived split and source provenance;
- pass the existing T065 public/model/action/replay validation.

Malformed or provenance-invalid rows fail closed. Nonterminal/truncated rows are
not selectable.

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

For audit identity only, a replay group may use:

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

Canonical JSON uses UTF-8, sorted keys, separators `(',', ':')`,
`ensure_ascii=False`, and `allow_nan=False`.

Ownership algorithm:

1. collect all selectable candidates from both source arms and every frozen
   split;
2. group globally by the unchanged replay-equivalence key;
3. sort each group by `member_order_key`;
4. if two distinct source rows have an identical complete `member_order_key`,
   fail Case D at `SELECTION_REPLAY`; do not invent another tie breaker;
5. otherwise the first member is the sole owner;
6. every non-owner is excluded before quota selection;
7. the owner keeps the split implied by its simulator seed;
8. inside each `(family, split)` owner bucket, sort by the same member order and
   take the frozen 48/16/16 quota.

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

Selected replay uses the frozen 16 shards x 20 selected-state partition. Process
concurrency is orchestration, not science: use up to 16 workers and report the
actual worker count. Worker PIDs, queue implementation, and process-binding
internals are not acceptance semantics.

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

Target generation keeps the frozen 16 x 20 selected-state shard partition and may
use up to 16 workers.

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
4. 10,000-stratified-bootstrap `p_positive >= 0.90` with
   `random.Random(655001)`;
5. the non-selected model seed aggregate mean paired delta `>= 0`;
6. zero hidden/schema/legal/replay/supported-screen-fallback violation.

A valid failure is Case C and Stage 6 is skipped.

### Conditional Stage-6 complete-run gate

Run only after a valid Stage-5 pass.

- fresh seeds: `651001..651256`;
- driver/fallback seed: `654002`;
- matched arms: stochastic, expert, learned-on-mandatory-families with expert
  fallback elsewhere;
- 16 fixed shards x 16 seeds per arm;
- up to 16 workers;
- 768 valid terminal runs required;
- bootstrap: 10,000 matched-seed resamples with `random.Random(655002)`;
- coverage: `L/D >= 0.60`, `F/M <= 0.01`, with `D != 0`, `M != 0` and the
  unchanged T065 D/L/M/F definitions.

A valid Stage-6 report passes only if:

1. matched mean terminal-floor delta `> 0`;
2. bootstrap `p_positive >= 0.80`;
3. learned Act-2 entry count `>=` expert;
4. zero controller errors and unreported truncations;
5. coverage passes;
6. at least one stronger signal holds: learned Act-2 count `>` expert or
   `p_positive >= 0.95`.

## Canonical Acceptance Model

T075 must have one production-side canonical acceptance model. CLI handlers,
artifact readers, validators, and finalization code must not each implement their
own copy of the state machine.

The implementation may choose exact Python names, but the model must be
structurally equivalent to these concepts:

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
  valid: bool
  passed: bool
  input_artifacts
  output_artifacts
  problems
  semantic metrics/evidence required by this contract

AcceptanceState =
  run_head
  completed stages
  current stage
  terminal case or none
```

There must be one pure or effectively pure transition authority equivalent to:

```text
advance(AcceptanceState, StageOutcome) -> AcceptanceState
```

Writers and CLI entry points may call that authority but must not redefine its
transition predicates.

### Legal transition table

```text
PREFLIGHT valid+pass       -> SOURCE_REUSE
PREFLIGHT invalid          -> D

SOURCE_REUSE valid+pass    -> SELECTION_REPLAY
SOURCE_REUSE invalid       -> D

SELECTION_REPLAY valid+pass -> TARGET
SELECTION_REPLAY invalid    -> D

TARGET valid+pass          -> TRAIN
TARGET invalid             -> D

TRAIN valid+pass           -> GATE
TRAIN invalid              -> D

GATE valid+pass            -> EVAL
GATE valid+fail            -> C
GATE invalid               -> D

EVAL valid+pass            -> A
EVAL valid+fail            -> B
EVAL invalid               -> D
```

For pre-gate stages, `valid=true, passed=false` is not a meaningful scientific
state and must not be emitted.

The central semantic distinction is:

```text
A = valid positive transfer result
B = valid Stage-6 negative result
C = valid Stage-5 negative result
D = invalid experiment / frozen-fidelity failure
```

B/C must never be represented as D merely because the learned policy performed
poorly.

### Terminal immutability

The first valid terminal state produced by the canonical acceptance model is
immutable. Once A/B/C/D is committed, later commands may validate/read/retain it
but may not recompute or reinterpret the terminal case.

A finalization/retention failure after a valid terminal decision is operational
failure. It does not rewrite the scientific terminal case.

## TARGET Transaction Barrier (Logical Stage 3)

Logical Stage 3 remains a mandatory commit barrier inside `TARGET`; it is not a
separate execution stage.

Target generation is not `TARGET valid+pass` until the persisted target table is
reopened and all of these checks pass:

1. strict target reader;
2. target completeness and no duplicate/missing rows;
3. selected-state lineage and exact 320-state family/split counts;
4. simulator/preflight/source lineage;
5. exact model-input schema;
6. 4737/92 state/action dimensions;
7. finite numeric values;
8. legal action order and one target per eligible action;
9. split-specific continuation seed contract;
10. public-input firewall.

The validation report must be persisted before TARGET is committed complete.

If the barrier fails:

- T075 ends Case D at `TARGET`;
- diagnostic target/validation files may remain as failure evidence;
- they must not become valid parents for TRAIN;
- no completed TARGET outcome is committed.

## Artifact And Execution Model

### One frozen scientific `RUN_HEAD`

No substantial T075 simulator/training stage runs until:

- production implementation is complete;
- the frozen executable acceptance boundary passes locally;
- the Maintainer has declared the implementation ready for scientific execution.

At that point record one exact Git `RUN_HEAD`. Every authoritative scientific
stage must run from that exact clean checkout and verify `HEAD == RUN_HEAD`.

If production code changes after scientific execution starts, authoritative
execution is reset. The Maintainer identifies the earliest semantically affected
stage; no artifact from an affected or downstream stage is reused under the new
head.

This replaces the rejected PR #75 pattern of allowing a growing implementation to
accumulate authoritative evidence across many code heads.

### Transactional stage execution

Each stage writes temporary/intermediate data outside the committed artifact set
and commits a `StageOutcome` only after the stage-specific validation succeeds or
produces a semantic invalid result.

A process interruption before a committed `StageOutcome` is operationally
incomplete, not a new scientific terminal case. The same frozen stage may be
rerun from the same valid parent artifacts and `RUN_HEAD` without changing
scientific settings.

A completed semantic/fidelity failure is different: it produces an invalid
`StageOutcome` and therefore Case D.

Do not build task-specific machinery to preserve every partial worker return,
PID, queue message, or temporary file as scientific evidence.

### Physical artifact identity

Persistent artifact identity is exactly:

```text
(role, normalized_path, sha256, size_bytes)
```

Paths are repository-relative POSIX paths under `artifacts/`, compared
case-sensitively. Normalize slash direction and `.`; reject `..`. Do not match by
basename only.

Content identities such as replay-group digest remain separate from physical file
identity.

### Minimal artifact lineage

The implementation must preserve the following semantic parent relationships;
it must not invent a generic recursive proof graph.

| Output | Required semantic parents |
|---|---|
| source-reuse report | exact two frozen T065 source files + PREFLIGHT |
| ownership audit | source-reuse report + PREFLIGHT |
| selected states / selection report | ownership audit + source-reuse report + PREFLIGHT |
| target table / TARGET validation | selected states + selection report + PREFLIGHT |
| training report/checkpoints | valid committed TARGET output |
| Stage-5 report | selected checkpoint + held-out targets/state identities |
| Stage-6 report | valid Stage-5 pass + selected checkpoint + frozen fresh seed set |
| terminal report | canonical acceptance state + reached-stage outputs |
| final retention manifest | terminal report + identities of all committed reached-stage outputs |

Required parent comparison uses `ArtifactIdentity`. There is no requirement for
per-stage retention manifests, recursive retention-manifest discovery, exact CLI
token matching, or a generic dependency/proof-chain framework.

### Frozen durable output surface

Use these stable roles/paths or a directly equivalent path approved before
implementation:

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
stage6-complete-run-report.json        # only if Stage 6 is reached
terminal-decision-report.json
t075-retention-manifest.json
```

The exact JSON serialization layout is implementation detail except where this
contract freezes scientific ordering, identity bytes, dimensions, or counts.
Schemas must be strict enough to fail closed on missing semantic fields, but
should not encode process-manager internals as experiment semantics.

## Allowed Implementation Freedom

The Implementer may choose:

- exact class/function names;
- the thin CLI spelling and subcommand layout;
- JSON field grouping for non-normative operational metadata;
- atomic-write helper details;
- process-pool/queue implementation;
- actual concurrency from 1 to the frozen upper bound when shard contents and
  numerical seeds are unchanged;
- whether small generic execution helpers already on main are reused.

The Implementer must keep the command layer thin. The command surface may invoke
stage adapters, the canonical acceptance model, and artifact IO; it must not
become a second workflow engine.

## Explicitly Forbidden Recovery Work

Do not:

- cherry-pick or mechanically port the rejected PR #75 T075 orchestration layer;
- preserve its large cluster of task-specific `_t075_*` lifecycle validators as
  the design;
- derive acceptance expected values from production helpers under test;
- add per-stage retention manifests solely to mirror PR #75;
- recursively search artifact lineage to rediscover exact inputs already frozen
  here;
- require exact command-string/token identity as scientific evidence;
- treat worker PID/process-binding details as scientific acceptance;
- create a generic workflow framework or task-numbered production package;
- change T075 science to make implementation easier;
- recollect Stage-1 sources;
- reuse PR #75 scientific runtime outputs as authoritative recovery evidence;
- run Stage 0-6 before the recovery implementation and executable acceptance
  boundary are frozen.

## Selective Salvage Boundary

Safe to consider for salvage after review:

1. the global-ownership scientific primitive and its canonical ordering helpers;
2. existing merged T065 readers, model-input code, target/training/evaluation
   primitives;
3. implementation-independent acceptance fixtures that encode frozen facts
   literally rather than via production helpers;
4. a generic spawn/process primitive only if it contains no T075 acceptance,
   artifact, or terminal semantics.

Default rewrite boundary:

- T075 command/orchestration layer;
- T075 terminal/finalization validators;
- T075 command matching;
- T075 path/retention traversal specific to PR #75;
- T075 partial-process evidence machinery;
- acceptance tests coupled to private production helpers.

If the Maintainer wants to salvage something outside the safe list, it must first
show that the code is a bounded implementation of an already-frozen row in this
contract. Otherwise report `ARCHITECTURE_ESCALATION` to the Planner.

## Normative Acceptance Matrix

Before production implementation, the Maintainer translates this matrix into an
implementation-independent executable boundary. Expected literals/fixtures must
not be generated by the production code being tested.

| ID | Scenario | Required result |
|---|---|---|
| A01 | exact frozen source files and metadata | SOURCE_REUSE pass |
| A02 | missing/hash-invalid/metadata-invalid source | D at SOURCE_REUSE |
| A03 | cross-split replay-equivalent raw candidates | one deterministic owner; not itself an error |
| A04 | exact full member-order tie between distinct rows | D at SELECTION_REPLAY |
| A05 | owner bucket below 48/16/16 quota | D at SELECTION_REPLAY |
| A06 | selected duplicate/cross-split replay overlap | D at SELECTION_REPLAY |
| A07 | all 320 selected states replay exactly | SELECTION_REPLAY pass |
| A08 | one selected replay mismatch | D; no replacement |
| A09 | TARGET table missing/duplicate/nonfinite/wrong action order | D at TARGET |
| A10 | TARGET public-input firewall or lineage failure | D at TARGET; TRAIN forbidden |
| A11 | TARGET generation exists but logical Stage-3 barrier not passed | TARGET is not complete; TRAIN forbidden |
| A12 | valid TARGET + valid training | GATE reached |
| A13 | valid Stage-5 pass | EVAL reached |
| A14 | valid Stage-5 fail | terminal C; EVAL absent |
| A15 | invalid Stage-5 evidence | terminal D |
| A16 | valid Stage-6 pass | terminal A |
| A17 | valid Stage-6 fail | terminal B |
| A18 | invalid/missing/truncated/controller-invalid Stage-6 evidence | terminal D |
| A19 | terminal already committed | later command cannot change A/B/C/D |
| A20 | final retention fails after valid terminal commit | operational failure; terminal case unchanged |
| A21 | process interruption before stage commit | no scientific terminal result; same frozen stage may rerun |
| A22 | StageOutcome/transition combination not listed by canonical table | reject as illegal state |
| A23 | public model input contains forbidden behavior/expert/target/hidden/future field | D at TARGET |
| A24 | production command/helper disagrees with canonical transition authority | implementation failure |

The acceptance suite may add focused implementation regressions, but a new
semantic row is a `CONTRACT_GAP` and must return to the Planner before production
changes continue.

## Verification Sequence

The recovery implementation proceeds in this order:

1. Planner contract only; no production code.
2. Maintainer execution-readiness review of this exact contract.
3. Test-only executable acceptance boundary implementing A01-A24.
4. Record baseline results against clean `main`/pre-implementation state where
   meaningful.
5. One bounded production implementation pass.
6. Local/focused tests and standard repository quality gates.
7. Full acceptance matrix review as a set, not validator-by-validator invention.
8. Freeze exact `RUN_HEAD`.
9. Run T075 scientific stages from that head only.
10. Materialize exactly one terminal A/B/C/D result and one final retention
    manifest.
11. Planner exact-head scientific/architecture acceptance.
12. Maintainer exact-head implementation/operational acceptance and merge.

No expensive Stage 0-6 execution begins before step 8.

## Review Finding Classification

After implementation starts:

- If this document already defines the correct behavior and code violates it:
  `IMPLEMENTATION_BUG`.
- If correct behavior is not unambiguously defined here: `CONTRACT_GAP`; stop
  production changes and return to Planner.
- If successive review passes reveal another new cross-module problem class,
  duplicated lifecycle semantics, growing validator glue, or loss of one
  canonical transition authority: `ARCHITECTURE_ESCALATION`; stop incremental
  patching.

A corrective implementation pass followed by a newly discovered cross-module
semantic class is presumed architecture escalation unless the Maintainer can
point to an existing acceptance row that already defined both behaviors.

## Required PR Evidence

The recovery PR must report:

- this contract commit and the exact implementation `RUN_HEAD`;
- proof that PR #75 production orchestration/runtime artifacts were not used as
  authoritative recovery state;
- retained T065 source identities and strict validation result;
- raw candidate/group/owner counts and post-owner family/split availability;
- selected 320-state counts and replay result;
- all reached target/training/gate/evaluation metrics;
- actual shard and worker counts plus wall-clock cost for substantial stages;
- exact terminal A/B/C/D;
- final artifact identities in `t075-retention-manifest.json`;
- any `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or `ARCHITECTURE_ESCALATION` raised
  during recovery;
- one next scientific recommendation only after a valid terminal result.

## Final Planner Review Checklist

The Planner will not provide scientific/architectural acceptance unless the
exact final head satisfies all of the following:

- T075 remains only the global-ownership cohort-partition repair scientifically;
- one canonical acceptance state/transition authority exists in production;
- terminal A/B/C/D semantics are not duplicated across CLI, validators, and
  finalization helpers;
- B/C remain valid negative science and D remains invalid experiment;
- logical Stage 3 is an atomic TARGET commit barrier;
- artifact lineage is explicit and minimal rather than recursive proof machinery;
- one exact `RUN_HEAD` owns authoritative scientific execution;
- acceptance expected values are implementation independent;
- command code remains thin and does not become a hidden workflow engine;
- process-manager details are not treated as scientific semantics;
- no hidden/human-policy information enters the deployable model;
- no T065 scientific constant frozen here changed;
- no authoritative runtime artifact from rejected PR #75 is reused;
- no unreviewed new semantic case was patched locally.

## Lifecycle

This recovery document is `DRAFT` until the Main Maintainer performs execution-
readiness review and posts exact-head `SPEC APPROVED` /
`implementation_authorized=true`.

That approval authorizes only bounded implementation against this contract. It
does not authorize the Maintainer or Implementer to redesign T075 semantics.

PR #75 remains an unmerged audit record and must be linked from the recovery PR.
