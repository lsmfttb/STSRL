# T075: Leakage-Safe Non-Combat Cohort Repair

## Objective

Repair the single cohort-partition defect exposed by T065 Case D and rerun the
unchanged learned non-combat experiment from the retained T065 Stage 1 source
evidence.

T065 did **not** fail because native replay, checkpoint restore, public
projection, model-input fidelity, source provenance, or the learned-policy
hypothesis was disproved. Its frozen source-selection rule treated any
replay-equivalent candidate observed in two seed-group splits as an invalid
experiment. The accepted T065 run found 107 such collisions (`MAP_SCREEN=19`,
`REWARDS=88`) even though the replay identity is already stricter than the model
input: it contains the complete `non-combat-model-input-v1` state, complete
public run context, and ordered legal-action identities.

T075 changes exactly one scientific rule: replay-equivalent source candidates
are globally deduplicated **before** per-split quota selection. Every replay
identity receives one deterministic owner candidate; all equivalent non-owner
candidates are excluded before the fixed 48/16/16 quotas are selected. Seed
split ownership remains frozen by simulator seed, so one simulator seed still
cannot cross train/validation/held-out, and one replay/model-equivalent state can
no longer cross them either.

Everything downstream of a valid 320-state cohort remains the T065 experiment:
all-eligible-action exact checkpoint continuations, the same public model input,
the same two fixed rankers, the same held-out gate, and the same conditional
three-arm complete-run evaluation.

T075 is a new experiment and does not reinterpret or reopen T065. T065 remains
`DONE` with its valid Case D.

## Publication Basis

Planner baseline for this proposal:

`95ccb6b55bc7a0214b632206ae169a533289fcf2`

T065 accepted evidence:

- approved T065 specification: `a13c92a66b4d9ad9f6a730293cadc8d66b4a699c`;
- merged T065 PR: #74;
- T065 merge commit: `d1b8a1e2e9714d88976379ceffa04d8038151286`;
- post-merge current-main status commit: `95ccb6b55bc7a0214b632206ae169a533289fcf2`;
- Stage 0 preflight SHA-256:
  `a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334`;
- stochastic Stage 1 source SHA-256:
  `40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61`;
- expert Stage 1 source SHA-256:
  `29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c`;
- accepted T065 Case-D decision report SHA-256:
  `0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc`;
- accepted T065 retention manifest SHA-256:
  `fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf`.

The T065 source run itself is valid and reusable. The final independent review
confirmed that the implementation, report fields, seed split assignment, replay
key, source lineage, native projection, and restore behavior were consistent.
T075 therefore does not authorize source recollection merely to obtain a more
convenient cohort.

## Research Question

After applying a leakage-safe deterministic global replay-group ownership rule
to the already valid T065 source pool, can the same frozen non-combat action-value
learning experiment obtain a valid held-out signal and, conditionally, transfer
that signal to fresh complete A20 runs?

The scientific question is unchanged from T065 after cohort construction. T075
must not tune the target, model, seeds, controller, thresholds, or screen scope
in response to the T065 Case D.

## Dependencies

Required merged dependencies:

- T033 public-context model-input encoder contract;
- T040 `expert_non_combat_v1`;
- T061 reachability bottleneck evidence;
- T064 terminal recommendation of non-combat learning;
- T071 stage/run-local artifact reuse convention;
- T074 acyclic decision/policy ownership;
- T065 learned non-combat workflow, exact model-input contract, retained Stage 1
  source artifacts, and accepted Case-D evidence.

T034 remains out of scope. T075 does not create a public-consistent hidden-future
sampler and makes no information-set-optimality claim.

## Immutable Reused Scientific Inputs

Unless explicitly overridden by the cohort-repair section below, the following
T065 values are frozen unchanged.

### Simulator and source configuration

- player class: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- controlled-run cap: `500` decisions/steps;
- Stage 1 simulator seeds: exactly `650001..650256`;
- source behavior driver seed: exactly `654001`;
- two source arms: `stochastic_non_combat_v1` and
  `expert_non_combat_v1`;
- battle controller:
  `OracleSearchController(simulations=20, root_selection_rule="highest_mean",
  action_space=ActionSpaceConfig.initial_no_potions())`;
- controller provenance name: `oracle_search_v1_highest_mean_s20`;
- source action-space identity is the exact T065
  `ActionSpaceConfig.initial_no_potions()` serialization;
- source collection topology: exactly 16 shards per arm, 16 source seeds per
  shard, at most 16 concurrent simulator workers.

The retained T065 Stage 1 source artifacts above are the required T075 source
inputs. Validate their hashes, retention manifests, approved T065 specification,
source seed range, driver seed, simulator identity, controller provenance,
action-space configuration, terminal/truncation counts, and shard topology
before selection. If either retained source artifact is absent, unreadable, hash
mismatched, or fails the existing strict source reader, T075 terminates Case D
with `stage=source-input-reuse`. Do **not** recollect Stage 1 inside T075.

### Seed-group split

Keep the exact T065 seed-group assignment:

- train seeds: `650001..650154`;
- validation seeds: `650155..650205`;
- held-out seeds: `650206..650256`.

Both source behavior arms for one simulator seed inherit that seed's split. No
simulator seed may cross splits.

### Mandatory learned families and quotas

Exactly four mandatory families:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

`BOSS_RELIC_REWARDS`, shop, event, card-select, and unknown/unsupported screens
remain expert-fallback only.

Selected-state quota per family remains exactly:

- train: 48;
- validation: 16;
- held-out: 16.

A valid cohort therefore contains exactly 320 selected states.

### Model input

Use exactly the merged T065 `non-combat-model-input-v1` contract:

- schema version: 1;
- tactical snapshot: `public-tactical-v2` v2 / `public-identity-v1`;
- public context: `public-context-model-input-v1` v1;
- snapshot dimension: 4634;
- public-context dimension: 103;
- state dimension: 4737;
- legal-action dimension: 92;
- state order: tactical snapshot then T033 public context;
- action order: existing public-tactical legal-action encoding;
- no extra screen embedding, expert feature/prior, behavior action, hidden field,
  learned identity embedding, or feature cross;
- training-split-only CPU float32 population mean/std normalization,
  `unbiased=False`, std clamped to at least `1.0`, then checkpointed and reused
  unchanged for validation, held-out, and online control.

### Continuation targets

Every selected state evaluates every eligible legal action from the exact same
restored checkpoint.

Continuation non-combat driver: `expert_non_combat_v1`.

Continuation driver seeds remain:

- train: `(652001, 652002)`;
- validation: `(652101, 652102)`;
- held-out: `(652201, 652202, 652203, 652204)`.

Target remains:

`q_floor = mean(max(0, terminal_floor - source_floor))`

No candidate-action subsampling, action replacement, alternate reward function,
or hidden-future resampling is permitted.

### Ranker

Model seeds remain exactly `(653001, 653002)`.

Topology remains exactly:

```text
state 4737 -> Linear(4737,64) -> ReLU -> Linear(64,64) -> ReLU
action 92 -> Linear(92,64) -> ReLU -> Linear(64,64) -> ReLU
concat -> 128 -> Linear(128,64) -> ReLU -> Linear(64,1)
```

No dropout, batch norm, residual, attention, ensemble, output activation, expert
prior, or architecture sweep.

Training remains:

- PyTorch CPU;
- `torch.manual_seed(model_seed)` before construction;
- PyTorch default `nn.Linear` initialization;
- `HuberLoss(delta=1.0, reduction="mean")`;
- `Adam(lr=1e-3, betas=(0.9,0.999), eps=1e-8, weight_decay=0,
  amsgrad=False)`;
- 1500 optimizer steps;
- 64 candidate-action rows per step;
- training row RNG: CPU `torch.Generator` seeded with
  `model_seed + 1_000_000`, `torch.randint(..., replacement=True)` semantics;
- gradient clip norm 10;
- `torch_threads=1`;
- no early stopping/checkpoint averaging;
- lower validation `q_floor` MAE selects the checkpoint; exact tie chooses lower
  model seed.

### Stage 5 held-out gate

Use the same 64 held-out states (16 per family after the repaired selection) and
same exact T065 gate:

1. aggregate mean paired `q_floor(model) - q_floor(expert)` > 0;
2. median paired delta >= 0;
3. at least three of four family mean deltas >= 0;
4. bootstrap `p_positive >= 0.90`;
5. non-selected model seed aggregate mean paired delta >= 0;
6. zero hidden/schema/legal/replay/supported-screen-fallback violations.

Bootstrap remains exactly 10,000 stratified source-state resamples using Python
`random.Random(655001)`, 16 held-out states with replacement per family in every
replicate, and
`p_positive = count(replicate_mean > 0.0) / 10000`.

A valid failed Stage 5 is Case C and skips Stage 6.

### Conditional Stage 6

Run only if Stage 5 passes.

Fresh simulator seeds remain exactly `651001..651256`, in exactly three matched
arms:

1. `stochastic_non_combat_v1`;
2. `expert_non_combat_v1`;
3. validation-selected `learned_non_combat_v1` on mandatory families with
   `expert_non_combat_v1` fallback elsewhere.

All Stage 6 arms use driver/fallback seed `654002`, the same frozen battle
controller/action space, A20 IRONCLAD natural starts, 500-step cap, and exactly
16 shards per arm x 16 seeds. At most 16 simulator workers may run concurrently.
A valid complete Stage 6 contains exactly 768 terminal runs.

The learned-vs-expert gate and bootstrap are unchanged from T065. Bootstrap uses
10,000 matched-seed resamples from `random.Random(655002)` and strict-positive
mean probability. Coverage remains exactly:

- `D`: all learned-arm non-battle decisions;
- `L`: mandatory-family decisions successfully selected by learned control;
- `M`: all mandatory-family decisions;
- `F`: mandatory-family learned-control schema/encoder/inference/action-coverage
  failures;
- `L / D >= 0.60`;
- `F / M <= 0.01`;
- `D == 0` or `M == 0` => Case D;
- unsupported fallback contributes to `D` only;
- battle decisions contribute to none of `D/L/M/F`;
- truncation/controller/illegal-action failures invalidate Stage 6 as Case D.

## The Only Scientific Change: Global Replay-Group Ownership

### Existing replay identity is retained exactly

Do **not** weaken or enrich the T065 replay-equivalence key. It remains:

```text
(
  screen_family,
  public_state_identity,
  ordered_legal_action_identities,
)
```

`public_state_identity` itself remains the SHA-256 identity of:

- the family;
- the complete 4737-value `non-combat-model-input-v1` state vector;
- the complete sanitized `public_run_context`;
- ordered legal-action identities.

This is intentionally at least as strict as model-input equality. Adding source
seed, behavior arm, occurrence, private checkpoint state, or action trace to the
replay-equivalence key merely to make collisions disappear is forbidden.

### Candidate validation before ownership

Load both retained Stage 1 arms through the strict current source reader. Every
candidate must retain its original T065 simulator seed, source arm, source run
identity, source step, family, split, public/model features, public context,
ordered legal identities, action trace, and source/controller provenance.

Before ownership, reject as Case D any malformed row, frozen-source provenance
mismatch, invalid mandatory-family projection, wrong model-input dimensions,
seed/split mismatch, hidden/private-field leakage, or invalid replay identity.

### Canonical candidate key

Reuse the exact T065 canonical source-candidate payload and selection key:

`sha256(b"T065-source-selection-v1\n" + canonical_candidate_json)`

where canonical JSON uses UTF-8, sorted keys, and compact separators. The
canonical candidate payload remains the T065 payload containing family,
simulator seed, source arm, public action trace, source step, public state
identity, and ordered legal-action identities.

No new RNG is used for ownership or selection.

### Global replay-group owner

Group **all** valid mandatory-family candidates from both source arms and all
three seed-group splits by the unchanged replay-equivalence key.

For each replay group:

1. compute every member's existing T065 `(selection_digest,
   canonical_candidate_json_bytes)` ordering key;
2. sort ascending lexicographically by that pair;
3. designate exactly the first candidate as the replay-group **owner**;
4. exclude every non-owner candidate from the selectable pool;
5. retain an audit record containing group digest, group size, all member source
   identities/splits/arms/seeds, owner identity/split, and exclusion count.

A replay group that spans multiple seed splits is therefore expected input to the
repair, not a fidelity failure. It is acceptable only because exactly one
canonical owner survives before quota selection. No result/target/model metric is
available or consulted at this stage.

This ownership rule also deduplicates same-split and same-arm repeats; there is
never more than one selectable candidate for one replay-equivalence key.

### Quota selection after global ownership

After ownership, partition surviving owners by their **existing simulator-seed
split** and family. Within every `(family, split)` bucket, sort by the same
existing `(selection_digest, canonical_candidate_json_bytes)` key and select the
first frozen quota (48 train, 16 validation, 16 held-out).

There is no Act/floor balancing, arm quota, manual substitution, strategic
quality filter, target-aware filter, or post-selection replacement.

If any repaired owner bucket has fewer than its frozen quota, terminate Case D at
`cohort-selection` and do not recollect sources or alter the ownership rule.

### Leakage and fidelity gates

A valid 320-state T075 cohort must satisfy all of these before Stage 2:

- exactly 48/16/16 states per family;
- exactly 320 states total;
- every simulator seed belongs to exactly its frozen seed-group split;
- both source arms for one simulator seed therefore remain in that same split;
- selected replay-equivalence keys are globally unique;
- no selected replay-equivalence key appears in another split;
- no source state is selected twice;
- each selected state replays to exact public/model state and ordered legal
  identities;
- no selected replay state may be replaced after a replay failure.

A selected-state replay failure remains Case D. The global ownership rule repairs
only pre-selection duplicate handling; it does not relax replay fidelity.

## Stage Topology And Reuse

### Stage 0 — retained-input/readiness validation

Validate:

- current pinned `sts_lightspeed` source identity;
- exact T065 approved spec/source provenance recorded by both retained source
  artifacts;
- exact source SHA-256 identities above;
- current `non-combat-model-input-v1` schema remains 4634/103/4737/92;
- T074 policy-boundary tests/import isolation remain valid;
- documented WSL Torch/native pairing remains usable;
- exact retained T065 Stage 0 preflight artifact is readable and consistent.

A fresh cheap current-runtime preflight may be rerun, but it cannot replace or
silently mutate retained Stage 1 evidence.

### Stage 1 — repaired cohort selection only

Do **not** run simulator source collection. Stream/read the exact two retained
Stage 1 artifacts, build global replay groups, assign canonical owners, select
48/16/16 per family, replay-verify the 320 selected states, and publish a new
T075 selection manifest.

This stage may use deterministic CPU parallelism for parsing/replay verification,
but ownership and final ordering must be deterministic independent of worker
completion order.

### Stage 2 — counterfactual targets

Same T065 topology: globally order the 320 selected states by mandatory family,
split (`train`, `validation`, `heldout`), then deterministic within-bucket
selection rank. Assign selected indices `0..319`.

Use exactly 16 shards, 20 selected states per shard. Each shard owns all eligible
actions and all required continuation seeds for its 20 states. At most 16
simulator workers.

Any missing action/continuation, restore failure, nonterminal 500-step
continuation, controller error, or non-finite target is Case D; do not drop or
replace rows.

### Stage 3 — model-input/target-table validation

No new learned feature design. Validate the exact T065 model-input schema,
complete target table, split/owner lineage, hidden-field firewall, and selected
replay uniqueness before training.

### Stage 4 — training

Exactly the two frozen model seeds and T065 ranker/training configuration above.
The two model processes may run concurrently, each with `torch_threads=1`.

### Stage 5 — held-out gate

Run the exact frozen T065 gate/metrics/bootstrap above. If it fails validly,
terminate Case C and skip Stage 6.

### Stage 6 — conditional matched evaluation

Run only after Stage 5 passes, using the exact frozen T065 256-seed x 3-arm
configuration and 16-shard topology above.

## Artifact Contract

Generated T075 artifacts remain ignored under a stable path such as:

`artifacts/t075-leakage-safe-non-combat-cohort-repair/`

The implementation must not copy the multi-GB T065 source artifacts into a new
location. T075 manifests reference the retained T065 source paths and exact
hashes.

Required compact artifacts:

- retained-source validation / reuse manifest;
- global replay-group ownership audit with counts by family/split/group size;
- repaired 320-state selection manifest;
- Stage 2 complete target report/table identity;
- normalizer identity;
- both model checkpoint/report identities;
- Stage 5 report;
- conditional Stage 6 report;
- terminal Case A/B/C/D report;
- final retention manifest linking all produced and reused artifacts.

Hashes are identity/reproducibility checks only; do not add proof chains or
security-style attestation.

## Terminal Cases

T075 ends in exactly one case.

### Case A — learned signal transfers

The repaired cohort is valid; Stage 5 passes; Stage 6 passes. Accept the learned
non-combat controller only as an experimental public non-combat policy with
expert fallback on unsupported families. Recommend Planner review of the
remaining battle-learning prerequisite(s) before any T066 joint-improvement
publication. Do not claim final natural-A20 or live promotion.

### Case B — offline signal does not transfer

The repaired cohort is valid and Stage 5 passes, but Stage 6 fails validly. Do
not promote the controller. Preserve the fixed evidence and recommend at most one
narrow diagnostic grounded in the observed transfer failure. Do not increase run
scale merely because 256 seeds are neutral.

### Case C — no held-out action-value signal

The repaired cohort and targets are valid, but Stage 5 fails. Skip Stage 6, do
not promote the controller, and close this v1 target/model formulation. Recommend
at most one narrow target/model diagnostic.

### Case D — invalid experiment

Any retained-source mismatch, insufficient post-owner `(family, split)` quota,
selected-state replay failure, target incompleteness, schema/hidden-field
failure, split leakage, simulator/provenance mismatch, truncation where forbidden,
or other frozen fidelity failure prevents valid attribution. Make no policy
conclusion, skip downstream stages, preserve completed stage manifests, and make
exactly one narrow repair recommendation.

Cross-split replay groups **before ownership** are no longer Case D. A
cross-split replay key **after ownership/selection** is Case D.

## Engineering Boundary

T075 is not permission to fork the T065 workflow.

- Reuse `src/sts_combat_rl/sim/non_combat_learning.py` and
  `src/sts_combat_rl/sim/non_combat_model_input.py`.
- Implement the repair as one explicit versioned cohort-partition strategy / pure
  selection helper in the existing neutral non-combat learning owner.
- Preserve the historical T065 strict selection reader/result semantics; do not
  rewrite the accepted T065 Case-D record.
- Do not copy T065 code into `t075_*` production modules.
- Do not add T075-specific routes/flags to the legacy flat CLI.
- A neutral existing `non_combat_learning` command may expose the new selection
  strategy explicitly without building a registry/framework.
- No battle/search/controller/model-input refactor is in scope.
- No source recollection is in scope.

## Out Of Scope

- changing replay-equivalence identity to hide duplicates;
- adding simulator seed/run/arm/private state/action trace to the model or replay
  identity merely to avoid leakage checks;
- source recollection or larger source scale;
- changing mandatory screen families;
- changing train/validation/held-out quotas;
- changing target, continuation policy/seeds, model input, architecture,
  optimizer, bootstrap, Stage 5/6 thresholds, Stage 6 seeds, battle controller,
  action space, or fallback policy;
- human trajectories, expert imitation labels, or strategy annotations;
- T063/T066 implementation;
- public-consistent hidden-future sampling;
- broad CLI/refactor/fixture/CI/license cleanup;
- 10,000-run natural scale-up or live deployment.

## Acceptance Criteria

T075 implementation may be accepted with Case B, C, or D; controller promotion
requires Case A.

Mandatory conditions:

- exact planner baseline and approved T075 spec are recorded;
- exact T065 source artifact hashes above are validated and reused; no source
  collection is executed;
- T065 replay-equivalence identity is byte/semantic compatible and unchanged;
- global replay groups choose exactly one canonical owner using the pre-registered
  T065 selection key;
- non-owner exclusion happens before per-split quota selection and uses no
  outcome/target/model information;
- seed-group split mapping remains exactly T065's;
- valid cohort has exactly 320 states and 48/16/16 per family;
- valid selected cohort has zero replay-equivalent cross-split overlap and zero
  simulator-seed split leakage;
- every selected state replays exactly with no replacement;
- if Stage 2 is reached, every eligible action receives every frozen continuation
  seed and the target table is complete;
- if Stage 4 is reached, exactly model seeds 653001/653002 use the frozen ranker,
  optimizer, minibatch RNG, and training-only normalizers;
- if Stage 5 is reached, exact frozen metrics/bootstrap determine pass/fail;
- Stage 6 runs iff Stage 5 passes;
- if Stage 6 runs, exactly 256 fresh seeds occur in all three arms with exact
  provenance/driver seed/shards and 768 valid terminal runs;
- terminal Case A/B/C/D is mechanically determined by the frozen rules;
- no large generated artifact is committed to Git;
- no task-specific legacy flat-CLI route is added;
- standard/focused tests, compileall, ruff, format, mocks, source verifier, and
  `git diff --check` pass where applicable.

## Required Tests

At minimum add focused tests for:

- replay-equivalence key unchanged from T065;
- global ownership of same-split and cross-split duplicate groups;
- deterministic owner independent of input order and worker completion order;
- owner split remains the owner's frozen seed-group split;
- all non-owner duplicates excluded before quotas;
- post-owner insufficient quota -> Case D;
- 48/16/16 quota selection with zero selected replay overlap;
- no simulator seed crosses splits;
- selected replay failure still Case D with no replacement;
- retained-source hash/provenance mismatch -> Case D;
- downstream T065 model/target/bootstrap/coverage constants remain unchanged;
- existing T065 historical Case-D reader/report regression remains valid.

## PR Report

The implementation PR must report:

- exact approved T075 spec and baseline;
- exact reused T065 Stage 0/Stage 1 paths and SHA-256 identities;
- retained-source validation results;
- total replay-group count, singleton/non-singleton counts, cross-split group
  count, candidate exclusions, and counts by family/split;
- deterministic owner-rule identity;
- post-owner available/selected counts per family/split;
- repaired selection-manifest hash and replay verification result;
- Stage 2 target counts/completeness/cost if reached;
- Stage 4 checkpoint hashes, model seeds, normalizer identity, training metrics,
  and validation checkpoint choice if reached;
- Stage 5 per-family/aggregate results and exact bootstrap probability if reached;
- whether Stage 6 ran;
- Stage 6 three-arm matched results, coverage, bootstrap, failures, wall-clock and
  simulator/search cost if reached;
- all shard/worker/reuse evidence;
- focused/full verification;
- exactly one terminal Case A/B/C/D and one next recommendation.

## Lifecycle

T075 remains `DRAFT` until the Main Maintainer independently approves the exact
specification head and records `implementation_authorized=true`. The Planner does
not dispatch implementation and this specification PR contains no feature code,
simulator execution, target generation, training, or evaluation.
