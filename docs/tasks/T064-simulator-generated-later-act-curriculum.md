# T064: Reuse-First Later-Act Curriculum Transfer

## Objective

Test one narrow hypothesis: whether changing only the order of exposure to
existing simulator-generated later-act data improves public policy/value
guidance relative to a static mixture with identical rows, initialization,
optimizer budget, and per-source exposure.

T064 is not a new data-generation, search, trainer, or evaluation framework.
It reuses the accepted T042 source pools, T043 teacher/trainer/checkpoint
contracts, T044 de-assisted evaluation, and T052/T069/T070 fixed Search v2
evaluation. New code is limited to parameterizing those paths where the current
interfaces are too rigid and to four compact T064 control/report artifacts.

## Current Baseline

T042 proved that the existing assistance schedules can produce later-act
starts. T043 established the teacher/trainer/checkpoint path. T044 established
de-assisted fixed-cohort evaluation, but its accepted checkpoint was trained
from four `assist_0` sources and did not consume the later-act pool. T070 showed
that deeper Search v2 traversal changes actions and tree geometry without
turning the existing learned guidance into better outcomes.

The missing experiment is therefore curriculum transfer, not another coverage
scale-up or Search v2 variant.

## Direct Dependencies

- T033 public-context model input and checkpoint compatibility;
- T042 assisted source pools, restore, coverage, provenance, and retention;
- T043 Oracle teacher, trainer bridge, model, checkpoint, and calibration;
- T044 de-assisted fixed-cohort evaluation;
- T052 frozen natural Boss/later-act cohort;
- T069 public-context projection;
- T070 Search v2 controller and fixed-cohort comparison semantics.

T008, T039, and T051 remain historical references. They are not runtime inputs
to T064. In particular, T064 does not regenerate the missing T039 artifacts.
The natural-distribution check is the frozen T052 holdout; the training anchor
is the accepted T042 `assist_0` control and remains labeled `assisted_run` /
`assist_0`, never `natural_run`.

No new native `sts_lightspeed` capability is required. The active integration
commit is `fee272f1ae21c283ad2161f55293cfe6d714134a`.

## Frozen Inputs

### T042 training candidates

The retained T042 manifest and pools are mandatory and must match:

- scale manifest SHA-256:
  `25efae30dc9a61c8b97cb09e1844b93b9ffe693bde51c0f494f0f65203a1d327`;
- `assist_0` pool SHA-256:
  `d124d94a94df534c0bcc32072582a4448746f0a9734a41410e45c51c1b1ff87f`;
- `assist_hp50` pool SHA-256:
  `1231bcd24309df9fbeb22ec56dfa12b661c38c6f440bdea1850053734cc32d8f`;
- `assist_hp50_potion_elite_boss` pool SHA-256:
  `642d11d4956316e96f58ddf5fceec94f59a50c3dd051205e2fdfca94485ab201`;
- `assist_hp75_potion` pool SHA-256:
  `1bbcbfebbde4fd2eec1be249f9843bf25a288abb0672950f47ad540c9bb8f46f`.

A missing or mismatched required pool is an integrity failure. T064 does not
regenerate a replacement pool or add another assistance schedule.

### Frozen holdouts

The holdouts are frozen before source selection, teacher collection, training,
or checkpoint outcomes:

- T044 `assist_0`: identity `a336ffb1fda9ed7e`, 21 records, SHA-256
  `4ee0eb125ac37e870f0f2c950290b131f4693185c60b6c71cd46b5265a4d0037`;
- T044 `assist_hp50`: identity `e99a0938307c0e7a`, 38 records, SHA-256
  `bc9372a67fe6b848616e4b700765d6a47f49b4044bd973dbcaff4dd3bba36`;
- T052 natural Boss/later-act: 93 records, SHA-256
  `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`.

### Initialization checkpoint

All four training runs initialize from checkpoint SHA-256
`a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`.
This retained checkpoint encodes model hidden size 16. T064 therefore freezes
hidden size 16 so the experiment preserves the exact accepted initialization;
there is no hidden-size migration or newly initialized replacement model.
The loader must retain every model parameter and registered normalization buffer
exactly. Optimizer state is always fresh. A required schema migration must be
deterministic and produce one identical migrated initialization for all runs;
otherwise execution is incomplete.

## Complexity And Reuse Boundary

Implementation begins with a concise reuse inventory in the PR report. It names
the existing function, schema, reader/writer, and tests used for each operation.
The inventory is report content, not a new standalone framework.

T064 assumes repository-owned stages and their in-repository callers are trusted
participants. Validation exists to catch accidental corruption, stale or
mismatched configuration, incomplete execution, and experiment-design drift; it
is not an adversarial attestation system. Existing hashes remain where they are
already part of accepted artifact identity or are useful for detecting stale
inputs, but T064 must not add duplicate proof artifacts, independent identity
chains, or caller-vs-producer distrust solely to make trusted in-repository
stages tamper-evident. Prefer deterministic derivation from authoritative inputs
plus ordinary schema, count, order, configuration, and completion checks.

The following thin extensions are authorized:

1. T043 teacher collection may accept an already-selected source manifest and a
   contiguous record range. Shards write the existing Oracle teacher rows and
   existing audit data. A deterministic merge reuses existing loaders/writers
   and requires identical configuration/provenance, disjoint complete ranges,
   exact selected-source order, and exactly one valid teacher row per selected
   source.
2. T044 evaluation may accept a cohort record range and a subset of its existing
   controller arms. Shard merge reuses `FixedEvaluationReport` and the existing
   de-assisted comparison report; it requires identical cohort/configuration,
   disjoint complete ranges, original cohort order, and no duplicate result.
3. The existing T070 shard runner may read expected checkpoint path and SHA-256
   from its frozen stage manifest instead of the historical constant. The old
   T070 manifest must still validate unchanged. T064 changes no controller,
   search, projection, root/leaf, RNG/chance, action-order, geometry, or failure
   semantics.
4. `train_torch_policy_value` may accept an initial compatible model/checkpoint
   and an explicit ordered batch plan. Without those optional arguments, its
   existing initialization and epoch-shuffle behavior remains unchanged.
5. The existing T043 trainer bridge may accept a T064 direct-provenance mode and
   a contiguous record range. In that mode the validated T064 curriculum
   manifest and merged Stage-2 teacher artifact are the authoritative inputs;
   source linkage is derived by code from `selected_sources` rather than
   accepted from a caller-authored T022/T023/source-pool identity mapping.
   Legacy T024/T043 manifest-driven behavior remains unchanged. Range outputs
   use the existing trainer-input schema and merge into one final existing-schema
   trainer input in exact selected-source order.

No parallel source pool, restore, coverage, teacher, trainer-input, checkpoint,
fixed-cohort, evaluation, Search v2, retention, or logging subsystem is allowed.
No new model architecture or checkpoint format is allowed. If implementation
requires a broader framework or a fifth T064-specific artifact contract, stop
and request specification reapproval rather than expanding scope.

## Complete Source Identity

`t064-complete-source-identity-v1` is embedded in the curriculum manifest. Its
required fields are:

- `source_checkpoint_id` string;
- `source_seed` integer;
- `source_run_id` string;
- `source_battle_index` integer;
- `action_trace_identity` string;
- `distribution_kind` string;
- `assistance_level` string, using `""` only when the source schema has no
  assistance field;
- `source_arm` string, using `""` only when the source schema has no source-arm
  field;
- `checkpoint_information_regime` string.

When an existing validated `action_trace_identity` is present, it is used
unchanged. Otherwise, derive it only from the existing validated selected-action
identity at each decision. The ordered hash input is a canonical JSON array of
objects containing `decision_index` and that decision's occurrence-safe
selected-action identity exactly as emitted by the repository action-identity
contract. Its per-decision `stable_id` and `occurrence` are preserved unchanged;
`occurrence` is scoped to duplicate legal actions within that decision and is
never recomputed across earlier trace entries. Missing or invalid occurrence-safe
identity, `stable_id`, or `occurrence` fails closed. Canonical JSON is UTF-8,
sorted keys, compact separators, no NaN/Infinity, and has no trailing LF in hash
input.

The complete identity SHA-256 is computed from the canonical JSON object above.
Two records are equal only when all required fields are equal. Existing pool and
cohort readers perform field mapping; a missing required value, ambiguous trace,
or incompatible provenance makes the record ineligible.

Candidate-inventory integrity and frozen-holdout exclusion are distinct:

- `candidate_duplicate_complete_identity_count` is computed over the complete
  T042 candidate inventory before holdout exclusion. It must be zero. A nonzero
  value is an integrity failure and makes T064 `INCOMPLETE`; candidate records
  are never silently deduplicated.
- `candidate_holdout_exclusion_count` is the number of candidate records whose
  complete identities match any frozen holdout identity. These matches are
  reported and excluded before bucket selection. A nonzero value is expected
  when a frozen holdout was drawn from a retained T042 pool and does not by
  itself make source adequacy false or constitute selected-training leakage.
- after final bucket membership is fixed,
  `selected_holdout_overlap_count` is recomputed from the flattened selected
  complete identities intersected with all frozen holdout identities, and
  `selected_duplicate_complete_identity_count` is recomputed from the flattened
  selected complete identities. Both must be zero. A nonzero selected overlap or
  selected duplicate count is an integrity failure and makes T064 `INCOMPLETE`,
  never scientific source-insufficiency Case B.

The manifest must retain enough identity evidence to reproduce each count and
prove which candidate rows were excluded and which final selected identities
were checked.

## Deterministic Selection

Eligibility requires A20, valid current-schema provenance, fresh restore,
replay-matched public context, valid structured outcome, and no recorded
controller/truncation/mapping/source/provenance failure. Selection never uses
battle result, terminal HP, teacher/model output, deck or relic quality, or
perceived winnability.

Three disjoint buckets are selected:

### `strong_later_act`

Take eligible Act-2+ records from `assist_hp75_potion`, ordered by complete
identity SHA-256, capped at 160.

### `medium_later_act`

For each of `assist_hp50` and `assist_hp50_potion_elite_boss`, take eligible
Act-2+ records ordered by complete identity SHA-256, capped at 32 per component.
Concatenate components in the order listed above.

### `anchor`

Use only eligible `assist_0` records. Group by
`(act, room_type, encounter_id, floor_bucket)`. For T064, `floor_bucket` is not
a coarse or learned bucket: it is the identity mapping of the raw persisted
`structural_metadata["floor"]` value. The input must be a Python integer but not
a Boolean, must satisfy `1 <= floor <= 56` with both boundaries inclusive, and
`floor_bucket = floor` exactly. No integer coercion, act-specific rebucketing,
or other boundary scheme is permitted. A missing `floor`, Boolean, non-integer,
or out-of-range value is an integrity failure that makes the experiment
`INCOMPLETE`; it must not be converted to `None`, silently excluded, or counted
as scientific source inadequacy.

Order strata lexicographically using their canonical JSON representation and
order records within each stratum by complete identity SHA-256. Repeatedly
traverse strata in that fixed order, taking the next unused record from each
non-empty stratum, until exactly 256 records are selected or all strata are
exhausted.

A complete source audit is scientifically valid even when post-exclusion
coverage is insufficient. `source_adequacy` is true only when:

- `strong_later_act` plus `medium_later_act` contain at least 128 unique records;
- `anchor` contains exactly 256 unique records;
- `selected_holdout_overlap_count == 0`;
- `selected_duplicate_complete_identity_count == 0`.

`candidate_holdout_exclusion_count` is not an adequacy gate. Candidate duplicate
identities, selected holdout overlap, or selected duplicate identities are
integrity failures; even if they make the adequacy Boolean false, the terminal
result is `INCOMPLETE`, not Case B. Source-inadequate Case B is permitted only
when candidate integrity is valid, selected leakage/duplicate checks are zero,
an exhaustive restore/context audit completes with zero integrity failures, and
the remaining inadequacy is solely a frozen post-exclusion coverage/cardinality
shortfall.

If an exhaustive valid audit completes under those conditions but source
adequacy is false, T064 may produce the complete-negative Case B without running
teacher/training stages. Invalid, missing, unaudited, or leakage-contaminated
evidence is `INCOMPLETE`, not Case B.

## Teacher And Trainer Construction

Use the existing T043 teacher and trainer bridge with:

- information regime `full_simulator_state_oracle_like`;
- search budget 100 for every source;
- root selection `highest_mean`;
- action space `initial_no_potions`;
- mandatory soft visit-distribution policy targets;
- existing separate behavior, policy, survival, terminal-HP, and structured
  resource fields;
- assistance and bucket metadata available only to selection, scheduling, and
  reporting, never to normal public model inputs.

Teacher collection uses 16 contiguous shards and 16 effective workers. Exact
ranges are generated from the final selected count and written into the
curriculum manifest before any teacher result exists. Every selected source must
produce one valid row. Missing, duplicate, invalid, or silently dropped rows are
integrity failures and leave T064 incomplete.

Stage 3 uses a direct T064 adapter to the existing T043 trainer conversion. Its
authoritative inputs are only the validated curriculum manifest after a
complete zero-failure selected-source audit and the linked merged Stage-2
teacher artifact. T064 does not require a caller-authored synthetic
`oracle-teacher-scaleup-manifest-v1`, synthetic T022 identity, synthetic
single-source-pool identity, or a newly persisted 460-row selected-pool artifact
solely to prove provenance between trusted repository stages. The existing
T024/T043 manifest-driven bridge remains unchanged for its historical callers.

Before conversion, Stage 3 must check the ordinary consistency conditions that
protect the experiment from accidental mismatch or drift:

- teacher row count equals the selected-source count;
- teacher rows match `selected_sources` in exact order and source identity;
- teacher configuration remains budget 100, `highest_mean`,
  `initial_no_potions`, and `full_simulator_state_oracle_like`;
- each selected source is restored with the already validated assisted replay
  path, and the restored snapshot/public context/legal actions match the source
  and teacher row as required by the existing T043 conversion;
- every emitted trainer row maps one-to-one, in order, to the selected complete
  source identity and retains the existing trainer-input schema.

Stage 3 is a substantial simulator restore stage and therefore uses the same 16
contiguous ranges as the selected-source/teacher inventory and 16 effective WSL
fork workers. Each worker converts only its range, atomically writes one
existing-schema trainer-input shard, and returns only a small persisted-shard
descriptor. The parent re-reads the shards through the existing trainer-input
reader, rejects missing/invalid/duplicate/out-of-order rows, and merges exactly
one final existing-schema trainer input in selected-source order. This is a
bounded range/merge extension of the existing bridge, not a new trainer-input
subsystem or T064 compact artifact.

The merged teacher dataset and trainer input retain their existing schemas. No
T064 teacher, trainer-input, selected-pool, T022/T023 adapter, or Stage-3 bridge
schema is introduced.

## Frozen Paired Training

Train `static_mixture_v1` and `assistance_annealed_curriculum_v1` for paired
seeds `64001` and `64002`, producing four checkpoints.

All runs use:

- the identical loaded initialization parameters and normalization buffers;
- CPU execution;
- `torch.use_deterministic_algorithms(True)` and one Torch CPU thread;
- `torch.manual_seed(seed)` and `random.seed(seed)`;
- existing model architecture with hidden size 16;
- Adam with learning rate `0.001`, betas `(0.9, 0.999)`, epsilon `1e-8`,
  weight decay `0`, and `amsgrad=false`;
- no learning-rate scheduler;
- batch size 32;
- 900 optimizer steps, divided into three phases of 300 steps;
- policy, outcome, HP, and resource loss weights all `1.0`;
- HP loss scale `100.0`;
- gradient norm clipping at `10.0`;
- existing target heads, loss functions, evaluation, and checkpoint writer.

Each phase therefore consumes 9,600 record draws. For each training seed and
bucket, build one deterministic exposure sequence of exactly 9,600 records by
repeated cycles. In cycle `k`, order bucket records by
`SHA256("<seed>:<bucket>:<k>:<complete_identity_sha256>")`. Append cycles until
9,600 entries exist and truncate exactly at 9,600.

Phase token patterns are repeated 3,200 times:

| arm | phase 1 | phase 2 | phase 3 |
|---|---|---|---|
| static | `strong, medium, anchor` | `strong, medium, anchor` | `strong, medium, anchor` |
| curriculum | `strong, strong, medium` | `strong, medium, anchor` | `medium, anchor, anchor` |

Each token consumes the next record from that bucket's exposure sequence. The
9,600 phase draws are chunked in order into 300 batches of 32. Across all three
phases, both arms consume every bucket exposure sequence exactly once, proving
identical per-bucket and per-source aggregate exposure. Any plan mismatch,
missing draw, duplicate batch position, or checkpoint/config mismatch is an
integrity failure.

The broad T009 training gate remains closed; this is a named narrow curriculum
diagnostic only.

## Frozen Evaluation

### T044 low-assistance cohorts

Use the existing T044 controller definitions and freeze:

- Oracle search simulations: 1;
- root selection: `highest_mean`;
- model-guided policy-probability weight: `0.1`;
- action space: `initial_no_potions`;
- maximum battle steps: 200;
- persisted `comparison_config.controller_roles` values exactly:
  `baseline_oracle_search`, `model_guided_search_t043_checkpoint`,
  `raw_checkpoint_public_policy`, and `scripted_public_policy_baseline`.

Existing controller/display labels remain whatever the current T044 command
emits; they are not persisted-role substitutes and are not changed by T064.

Checkpoint-independent baseline and scripted results are reused from accepted
T044 reports only when cohort SHA/identity/order, source format, action space,
maximum steps, controller provenance, the exact persisted role map above,
search budget/root/weight, information regime, and zero-failure status all
match. Otherwise each such arm is rerun once per cohort, not once per checkpoint.

For every new checkpoint, run only the two checkpoint-dependent arms on both
cohorts. Each checkpoint/cohort stage uses 16 shards and the following frozen
ranges:

- 21-record `assist_0` cohort:
  `0:2,2:4,4:6,6:8,8:10,10:11,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19,19:20,20:21`;
- 38-record `assist_hp50` cohort:
  `0:3,3:6,6:9,9:12,12:15,15:18,18:20,20:22,22:24,24:26,26:28,28:30,30:32,32:34,34:36,36:38`.

Merge retains the existing T044 report schema and original cohort order.

### T052 natural Boss/later-act cohort

For each checkpoint run only T070-compatible `prior_value` on the frozen T052
cohort with budget 100, geometry disabled, T069 projection enabled, and all
accepted T070 controller/root/leaf/RNG/chance/action-order/failure semantics
unchanged. The 16 frozen contiguous ranges are:

`0:6,6:12,12:18,18:24,24:30,30:36,36:42,42:48,48:54,54:60,60:66,66:72,72:78,78:83,83:88,88:93`.

Use 16 effective workers.

The accepted T070 baseline is reused only when its report validates:

- report schema and complete 93-record cohort SHA/identity/count/order;
- source manifest and native runtime identities;
- budget 100, baseline ablation, action space, geometry setting, root/leaf,
  RNG/chance, action ordering, and failure policy;
- exact shard ranges and zero failures;
- compatibility tests proving the parameterized runner still accepts the old
  T070 frozen manifest without changing its expected historical checkpoint.

A T064 stage manifest supplies the evaluated checkpoint path and SHA-256 while
freezing every other T070 field. No high-budget, cost recalibration, or geometry
stage is run.

## Completeness And Transfer Gates

`experiment_complete` requires valid inputs, complete source audit, source
adequacy, complete teacher/trainer artifacts, exact exposure parity, four valid
checkpoints, complete evaluations, and zero integrity/execution failures.

When `experiment_complete=true`, curriculum transfer is true only if:

1. summed curriculum `prior_value` wins on T052 are at least two above paired
   static wins;
2. neither curriculum seed is more than one T052 win below its paired static
   seed;
3. aggregate curriculum-minus-static win deltas are non-negative on both the
   88-record Boss and 5-record Act-2+ T052 subsets;
4. summed curriculum model-guided wins on T044 `assist_hp50` are at least two
   above paired static wins;
5. curriculum raw-public-policy wins on T044 `assist_hp50` are not below static;
6. curriculum model-guided wins on T044 `assist_0` are no more than one below
   static.

Terminal HP, structured resources, policy/value calibration, model calls,
simulator steps, root visits, and wall-clock cost are mandatory diagnostics but
cannot replace these gates.

## Terminal Decision

- **Case A — transfer demonstrated:** `experiment_complete=true` and every
  transfer gate passes. Recommend `T063-oracle-guided-public-battle-learning`.
- **Case B — complete valid negative:** either a complete exhaustive source
  audit finds source adequacy false solely from valid post-exclusion
  coverage/cardinality shortfall after candidate-integrity and selected-leakage
  checks pass, or `experiment_complete=true` and at least one transfer gate
  fails. Recommend `T065-learned-non-combat-policy-v1`.
- **INCOMPLETE:** missing/invalid artifacts, provenance mismatch, candidate
  duplicate identities, selected holdout overlap, selected duplicate identities,
  code defect, OOM, interruption, incomplete shards, training/checkpoint
  failure, exposure mismatch, or incomplete evaluation. Emit no planner
  recommendation. Repair on this PR or obtain specification reapproval.

T064 emits exactly one of Case A, Case B, or INCOMPLETE. Only Case A/B are valid
accepted research outcomes.

## Compact T064 Artifacts

T064 defines exactly four compact JSON file paths under the stable T064 artifact
root. There is one file instance per schema, not one training-report file per
run. They use UTF-8, LF, sorted keys, compact separators, required `schema_id`
and `format_version=1`, reject an unsupported version, and fail closed on
missing required fields. Existing large teacher, trainer, checkpoint, T044, and
T070 artifacts retain existing schemas. An early integrity failure may leave a
later file unproduced, but no fifth T064 compact JSON file is authorized.

1. `t064-curriculum-manifest-v1`
   - input paths/hashes and native/code identities;
   - frozen holdout identities;
   - complete source identities and exclusion reasons;
   - `candidate_holdout_exclusion_count` plus identity evidence for excluded
     candidate rows, and `candidate_duplicate_complete_identity_count`;
   - selected bucket membership and structural counts;
   - `selected_holdout_overlap_count` and
     `selected_duplicate_complete_identity_count` recomputed from flattened
     final selected membership;
   - source-audit status, adequacy result, teacher shard ranges;
   - exact exposure-sequence and batch-plan hashes.
2. `t064-training-run-report-v1`
   - one aggregate document with a required `runs` array;
   - deterministic run order exactly:
     `static_mixture_v1/64001`,
     `assistance_annealed_curriculum_v1/64001`,
     `static_mixture_v1/64002`,
     `assistance_annealed_curriculum_v1/64002`;
   - each run entry contains arm, seed, initialization hash, full frozen
     optimizer/configuration, trainer-input and batch-plan hashes,
     per-bucket/per-source exposure counts, checkpoint path/hash and existing
     checkpoint metadata linkage, completion status, and problems;
   - if source adequacy is false and training is correctly skipped, `runs` is an
     empty array and `not_run_reason="source_inadequate"` is required.
3. `t064-stage-summary-v1`
   - concise reuse inventory;
   - stage name/status, exact command, code/native identity, inputs/outputs;
   - workers, shards, ranges, return codes, wall-clock and failure counts;
   - referenced existing artifact schema/path/hash/bytes;
   - failed attempts and retained log paths;
   - retention reason, downstream consumer, and deletion condition.
4. `t064-transfer-decision-v1`
   - source adequacy, completeness, every transfer gate and diagnostic summary;
   - Case A, Case B, or INCOMPLETE;
   - exactly one recommendation only for Case A/B;
   - problems and unmet acceptance criteria.

A separate T064 log-index, retention, teacher-merge, evaluation-merge, per-run
training-report, or source-identity framework is prohibited; those facts live
in the four files above or in the existing reused artifacts.

## Execution Topology

Use stable ignored root:

`artifacts/t064-later-act-curriculum-transfer/`

Stages are:

0. verify retained inputs, runtime, holdouts, and initialization;
1. build curriculum manifest and run 16-shard selected-source restore/context
   audit;
2. run and merge 16-shard T043 teacher collection;
3. run 16-shard direct T064-to-T043 trainer conversion from the validated
   curriculum manifest plus merged teacher artifact, merge one existing-schema
   trainer input in exact selected-source order, then validate the frozen batch
   plans;
4. run four deterministic training jobs and write the single aggregate
   `t064-training-run-report-v1` after all four run outcomes are known;
5. validate/reuse checkpoint-independent T044 arms, then run eight
   checkpoint-dependent T044 stages;
6. validate/reuse T070 baseline, then run four T052 `prior_value` stages;
7. aggregate decision and independently rehash the four compact T064 files plus
   every referenced existing artifact.

Interrupted or failed attempts are retained separately and never mixed into an
accepted rerun. The Stage-0 manifest produced before the holdout-scope
clarification is explicitly non-evidence; it must remain under
`logs/failed-attempts` with its exact SHA-256 recorded in the stage summary and
final PR report, and none of its records or adequacy conclusion may contribute
to an accepted rerun. Non-simulator manifest, merge, training, aggregation, and
hash steps may be single-process. Substantial simulator stages use 16 effective
workers and 16 shards.

### Stage-Affect Boundary And Approved Reuse

Git commit fields are producer and execution provenance. A curriculum
manifest's `code_commit` records the Stage-0 producer and is never rewritten to
claim that an older artifact was produced by a later head. A producer commit
that differs from the current approved execution head is not, by itself, a
reason to reject reuse. Reuse still requires the ordinary schema, frozen-input,
configuration, hash/byte, row/order/linkage, worker/range, return-code, and
zero-problem checks defined by this task.

For each reviewed repair, the planner and maintainer name an
`earliest_affected_stage`. Strictly validated outputs before that boundary may
be reused with their original producer provenance; the affected stage and all
downstream stages are rerun. If the reviewed diff or cheap readiness checks
cannot prove that boundary, execution stops for a narrower determination or
moves the boundary earlier.

The checkpoint-root repair introduced at
`dce4a818f2c107073030fbede3fc98a32d84a664` changes only Stage-4 preflight and
checkpoint publication. Its `earliest_affected_stage` is 4. The accepted
Stage-0 manifest, Stage-1 restore audit, Stage-2 teacher, and Stage-3 trainer
input from the preceding producer head are therefore reused after strict
reader/rehash/linkage validation; they are not regenerated or relabeled.

Before formal Stage 4--7 execution, run one cheap readiness pass that verifies:

- the local and remote execution head equal the exact head named in the latest
  planner/maintainer approval comment;
- no formal T064 process is active and every Stage-4--7 output target is absent
  or separately retained as failed evidence;
- reused Stage-0--3 artifacts pass their existing strict readers, hashes,
  bytes, row/order/linkage checks, frozen 16-worker ranges, return codes, and
  zero-problem gates;
- every frozen Stage-4--7 input path exists and retains its published identity,
  including the initialization checkpoint, both T044 cohorts and historical
  reports, the T052 cohort, and the T070 manifest, baseline, native-preflight,
  source, and wrapper inputs;
- the frozen initialization checkpoint is actually loaded and its hidden size,
  state/action normalizers, encoders, and policy/outcome/HP/resource head shapes
  match the frozen Stage-4 architecture;
- every Stage-4--7 output and checkpoint directory can be created and written;
  use a uniquely named, refuse-overwrite probe and remove only that probe after
  the check, without creating a compact artifact;
- the existing checkpoint writer completes one tiny save-and-load round trip,
  and the Stage-4 preflight regression passes without training;
- the existing Stage-5 production-plan route loads both frozen T044 cohort
  contracts and their exact action/controller configurations, and each
  checkpoint/cohort selector resolves exactly one dependent stage;
- the existing Stage-6 route loads the T070 wrapper and both its historical
  frozen identity and current checkpoint-selection identity without confusing
  producer and execution commits;
- the real Stage-7 aggregator accepts representative complete fixture/mock
  inputs and derives a complete terminal decision; and
- the existing one-record-range T044 simulator-dependent route smoke passes
  with its test adapter. A real WSL one-record smoke may additionally be used
  when useful, but it is not a substitute for the frozen 16-worker formal
  Stage-5/6 execution.

The corrected task document and exact-head approval are both required before
formal execution resumes. The readiness pass must finish before the first
expensive Stage-4 run; no additional ordering between approval and readiness is
required. Readiness and approval are workflow evidence, not a fifth compact
artifact or a new attestation framework.

## Out Of Scope

- T039 regeneration or new natural source collection;
- new assistance schedules, source schemas, teacher formats, trainer-input
  formats, checkpoint formats, model architectures, or evaluation formats;
- adversarial artifact attestation, duplicate provenance proof chains, or
  additional sidecars whose only purpose is to distrust another trusted
  repository-owned stage;
- Search v2 changes, budget tuning, cache/batching/projection work, or native
  tree changes;
- human trajectories, action labels, win-rate tables, or handcrafted strategic
  labels/rewards;
- treating `assist_0` or any assisted/constructed data as natural coverage;
- complete-run A20, live-game, controller-promotion, or final-agent claims;
- broad repository refactoring inside this experiment.

Local refactoring is permitted only when it directly parameterizes an existing
path and reduces duplication. Broader simplification should be proposed as a
separate planner task after T064 only if implementation evidence shows repeated
orchestration/contract duplication across multiple task paths. That follow-up
must explicitly audit over-defensive validation and provenance design as a
maintenance risk: duplicated truths, repeated rehash/cross-link glue, brittle
reruns, blocked iteration, and code paths whose only value is defending against
a malicious in-repository producer should be candidates for removal or
simplification while retaining checks that catch realistic accidental errors and
design drift.

## Acceptance Criteria

T064 is accepted only when:

- no parallel T042/T043/T044/T070 subsystem or fifth T064 artifact contract was
  introduced;
- all required retained input hashes match;
- holdouts precede selection/training, candidate holdout exclusions are reported
  separately from selected leakage, and final selected holdout overlap is zero;
- candidate duplicate complete identities and selected duplicate complete
  identities are zero;
- complete source identity, selection, and batch plans are deterministic;
- Stage 3 derives its linkage from the validated T064 manifest plus merged
  teacher artifact, uses no caller-authored synthetic provenance contract, and
  produces exact one-to-one selected-source/trainer-row order;
- static and curriculum arms differ only in exposure order;
- reused artifact schemas and merge invariants pass compatibility tests;
- required simulator stages use the frozen ranges and 16 workers;
- the terminal output correctly separates valid post-exclusion source
  insufficiency Case B from leakage/integrity `INCOMPLETE`;
- no prohibited performance or natural-distribution claim is made.

## Required Verification

Run the standard suite, compileall, Ruff check/format, fixture smokes, task-doc
checks, and `git diff --check`, plus focused tests for:

- source identity, candidate holdout exclusion versus selected overlap,
  candidate/selected duplicate detection, deterministic bucket selection, exact
  raw `floor` identity mapping to `floor_bucket`, and fail-closed invalid-floor
  handling;
- source adequacy recomputation that ignores candidate holdout exclusions but
  requires zero selected overlap/duplicates, and routes any leakage/integrity
  failure to `INCOMPLETE` rather than source-negative Case B;
- existing per-decision occurrence-safe action identity reuse and fail-closed
  trace fallback;
- T043 teacher range collection/merge and direct T064 trainer range conversion,
  assisted restore, exact selected identity/order merge, and legacy T024/T043
  default-path compatibility;
- Stage-3 script-level 16-fork execution proving it reaches the existing T043
  conversion without a caller-authored synthetic bridge contract;
- checkpoint initialization and default-training backward compatibility;
- deterministic batch plans and exact exposure parity;
- exact T044 persisted role strings, frozen ranges, and range/arm-subset merge
  compatibility;
- manifest-driven T070 checkpoint substitution and unchanged old-manifest
  validation;
- aggregate four-run training report cardinality/order;
- completeness, Case A/B, and INCOMPLETE decision logic;
- independent artifact rehash.

## Lifecycle And PR Contract

T064 remains `DRAFT` on merged `main` throughout this open PR. There is no
intermediate specification merge. Implementation begins only after an exact
`SPEC APPROVED` comment for a specific commit on this PR. Before accepted final
merge, the same PR updates the task index to the direct dependency set above and
records T064 as `DONE` with its terminal result.

Known acceptance risks before implementation are:

- holdout exclusion may reduce eligible later-act sources below 128;
- teacher budget 100 may expose runtime or memory limits;
- the existing checkpoint may be compatible but provide no transfer benefit;
- historical T044/T070 baseline reuse may fail strict identity validation and
  require one checkpoint-independent rerun per cohort;
- T052 has only five Act-2+ records, so subset conclusions remain diagnostic.

## PR Report

Before final review, the pull request report must summarize the accepted T064
result using existing artifacts and the four compact T064 files; this section is
reporting policy only and does not authorize another artifact or execution
surface. It must include:

- task ID, approved specification commit, final implementation head, and merge
  base;
- reuse inventory naming each existing T042/T043/T044/T052/T069/T070 module,
  command, schema, reader/writer, and compatibility test used;
- verified retained-input paths, SHA-256 identities, native/runtime identities,
  and holdout identities;
- `candidate_holdout_exclusion_count` with component/identity evidence,
  `candidate_duplicate_complete_identity_count`,
  `selected_holdout_overlap_count`, and
  `selected_duplicate_complete_identity_count`, plus the final selected
  zero-leakage/zero-duplicate proof;
- selected source counts by bucket, component, act, room/encounter stratum, and
  the final source-adequacy result;
- teacher budget/configuration, teacher and trainer-input identities, row counts,
  failures, and all four checkpoint identities;
- Stage-3 direct-provenance disposition: validated curriculum-manifest/teacher
  linkage, 16-shard restore/conversion evidence, exact trainer-row identity/order,
  and confirmation that no synthetic caller-authored bridge contract or extra
  provenance-only artifact was used;
- the exact paired training configuration, initialization identity, seeds,
  phase/batch-plan hashes, per-bucket and per-source exposure-parity result;
- T044 outcomes for both frozen cohorts and T052/T070 `prior_value` outcomes,
  including required subset diagnostics and checkpoint-independent baseline
  reuse/rerun disposition;
- for every substantial simulator stage: workers, shards, exact ranges,
  wall-clock seconds, return/failure counts, and referenced artifact hashes;
- `experiment_complete`, every frozen transfer gate, and the terminal Case A,
  Case B, or INCOMPLETE result, with exactly one recommendation only for Case
  A/B;
- SHA-256 identities for each of the four compact T064 JSON files and every
  referenced retained artifact used as final evidence;
- failed/interrupted attempts, including the pre-clarification failed Stage-0
  manifest path and SHA-256, and why none contributed records or conclusions to
  accepted reruns;
- verification commands/results, known limitations, unresolved risks, and every
  unmet acceptance criterion.

The PR report must distinguish historical accepted evidence from commands run on
the implementation head and must not turn missing/incomplete evidence,
candidate holdout exclusions, or selected leakage/integrity failures into a
scientific Case B.
