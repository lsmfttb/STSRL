# T086: Minimal Self-Generated Non-Combat Policy Improvement

## Objective

Build the first scientifically qualified learned Non-Combat policy after T085, while freezing Battle to the strongest accepted non-learned baseline.

T086 asks one question:

> With Battle fixed to unguided Search v2, can a public-information action-conditioned Non-Combat ranker trained only on simulator-generated counterfactual continuation returns outperform `expert_non_combat_v1` on held-out decisions and then improve fresh matched A20 complete-run progress?

This is deliberately narrower than T066. It does not couple learned Battle and Non-Combat policies, does not reopen the closed T085 Battle value-repair round, and does not claim a complete joint self-improvement loop.

The experiment is self-generated. Human trajectories, human action labels, hand-authored card/deck rankings, and imitation loss on `expert_non_combat_v1` are forbidden. `expert_non_combat_v1` is allowed only as source/continuation behavior, explicit fallback on unsupported screens, and the frozen comparison baseline.

## Publication Baseline

Planner publication base:

`main @ b38c0584e4aac9172f9da4426004bfb64a13a41d`

Accepted active simulator identity:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d62ff35579b54d70a7428afdf84743c94df3fe0c`

T085 is complete with `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`. Therefore no T085 learned value, prior/value arm, root-prior allocation variant, or historical learned Battle checkpoint may be used by T086.

## Dependencies

Required accepted dependencies:

- T033: public-context model-input encoding.
- T040: `expert_non_combat_v1` bootstrap/fallback behavior.
- T065: normative `non-combat-model-input-v1` schema and the existing small action-conditioned ranker design.
- T075: exact leakage-safe 320-state selected Non-Combat cohort and global replay-group ownership.
- T076/T078: restored-state branch isolation and public-context/legal-action fidelity repair.
- T074: acyclic policy/control ownership.
- T081: artifact eligibility gate.
- T085: current Battle-side disposition and accepted unguided baseline.

T066 is explicitly **not** a dependency and remains DRAFT. T086 must finish before Planner reconsiders joint/alternating learning.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: exact T075 selected cohort identity; exact T065 `non-combat-model-input-v1` schema; exact T078 restore/public-context semantics; exact T085/main/native Battle baseline identities; all T086 target, checkpoint, held-out, complete-run, report, and retention identities.

Reuse mode: `scientific_quality_claim`.

Claim boundary: T086 may establish only whether this bounded four-family public Non-Combat ranker improves simulator-derived continuation value and fresh matched A20 run progress with Battle frozen to unguided Search v2. It does not establish Heart win-rate improvement, all-screen Non-Combat optimality, Battle improvement, live-game readiness, or a joint policy-improvement loop.

Required predicates: reused state identities and split ownership must match the accepted T075 cohort; all 320 reused states must revalidate under the current native identity before target generation; deployable input must match the exact public T065 schema; Battle controller semantics must remain frozen; target rows must be complete for every eligible action and required continuation seed; model selection must use validation only; held-out and fresh-run evaluation must use frozen identities/seeds; all retained artifacts must pass provenance and eligibility checks.

Unavailable-fact behavior: any required identity, restore/public-context/legal-action parity fact, target row, model-input compatibility fact, checkpoint provenance field, evaluation result, or retained artifact that is unknown, stale, conflicting, malformed, filename-inferred, or unavailable fails closed to `INCOMPLETE`. A valid experiment whose fresh learned-control coverage cannot satisfy the explicit support gate maps only to `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`.

## Frozen Battle Side

Every counterfactual continuation and every fresh complete-run evaluation arm uses the same Battle policy:

- Search implementation: native `BattleScumSearcher2` / Search v2;
- nominal simulations: `100`;
- root selection: `highest_mean`;
- policy prior callback: none;
- learned leaf-value callback: none;
- rollout continuation: native `playoutRandom`;
- terminal utility: native `evaluateEndState`;
- action space: `ActionSpaceConfig.initial_no_potions()`;
- current pinned simulator/native identity above.

This is the frozen Battle side for T086. Search@400 is not part of this experiment. T086 may report Battle cost but may not alter Battle search budget, topology, utility, prior, value, RNG/chance semantics, or action legality in response to Non-Combat results.

## Reused Non-Combat State Substrate

Reuse only the exact accepted T075 selected cohort:

- 320 selected states;
- exact selection SHA-256: `94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8`;
- four families: `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`;
- per family: 48 training, 16 validation, 16 held-out;
- global replay-group ownership from T075 remains authoritative.

Historical T065/T075/T077 target/outcome artifacts are not training labels for T086 and must not be reinterpreted as though they were produced under the current Battle/native identity.

### Mandatory current-native revalidation

Before any target continuation is executed, replay/restore all exact 320 states under `d62ff355...` and require exact equality for:

- retained public decision context;
- ordered legal-action identities;
- screen/family identity;
- public model-input-relevant fields;
- replay/source identity.

No state may be replaced, dropped, re-ranked, or moved between splits.

If any state fails this gate, stop as `INCOMPLETE`. T086 does not reopen source collection or repair simulator fidelity inside the same scientific task unless Planner materially amends the contract.

## Supported Learned-Control Scope

Learn exactly the same four families as the T065 v1 public learner:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

All other non-battle screens use explicit `expert_non_combat_v1` fallback and must be reported as fallback decisions rather than silently attributed to the learned policy.

No supported family may be reclassified as fallback because a model score is inconvenient.

## Model Input

Reuse the exact T065 normative `non-combat-model-input-v1` contract without feature redesign:

- state input = public tactical/context state, dimension `4737`;
- action input = public legal-action compatibility vector, dimension `92`;
- no hidden simulator state, RNG state, future encounter information, checkpoint payload, expert score/prior, behavior action, or target may enter deployable input;
- training-only normalization is fit on T086 training rows only and frozen into the checkpoint;
- validation, held-out, and fresh-run inference must use that exact checkpointed normalization.

Any schema/version/size mismatch is `INCOMPLETE`.

## Counterfactual Target

For every reused state and every eligible legal action:

1. restore/replay the exact source state and verify public/legal identity;
2. capture the canonical process-local checkpoint;
3. restore that same checkpoint before each candidate branch;
4. force the candidate action exactly once;
5. continue to terminal with frozen Battle Search v2@100 and `expert_non_combat_v1` for later Non-Combat decisions;
6. compute additional terminal-floor progress:

```text
q_floor = mean(max(0, terminal_floor - source_floor))
```

The target is simulator-derived continuation progress. It is not a hand-written reward over cards, relics, HP, gold, or deck quality.

Every candidate action within one source state uses the same ordered continuation seed set (common random numbers). Candidate actions may not be capped or subsampled.

### Frozen continuation seeds

- training states: `(862001, 862002)`
- validation states: `(862101, 862102)`
- held-out states: `(862201, 862202, 862203, 862204)`

Missing/non-terminal branches, restore mismatch, controller failure, illegal action, non-finite target, or missing required seed row fails closed to `INCOMPLETE`. No branch or state replacement is allowed.

The exact future simulator state at the branch point is checkpoint-fixed; this does not constitute public-consistent hidden-future averaging and T086 must state that limitation.

## Model And Training

Use the existing small T065 action-conditioned ranker architecture unchanged:

```text
state[4737]
  -> Linear(4737,64) -> ReLU
  -> Linear(64,64) -> ReLU

action[92]
  -> Linear(92,64) -> ReLU
  -> Linear(64,64) -> ReLU

concat(state_embedding, action_embedding)
  -> Linear(128,64) -> ReLU
  -> Linear(64,1)
```

Train exactly two seeds:

- `863001`
- `863002`

Frozen optimization:

- PyTorch CPU;
- Huber loss, delta `1.0`;
- Adam `lr=1e-3`, betas `(0.9,0.999)`, eps `1e-8`, weight decay `0`;
- batch size `64` action rows sampled with replacement;
- exactly `1500` optimizer steps;
- gradient clip norm `10`;
- one Torch thread per model;
- no early stopping, hyperparameter sweep, architecture sweep, checkpoint averaging, or post-held-out model selection.

Checkpoint choice is made before held-out results using validation `q_floor` MAE only. Exact tie chooses lower seed. The non-selected seed remains a robustness diagnostic.

The deployed policy scores all eligible actions on supported screens and takes the highest predicted `q_floor`; exact score ties use the lowest legal-action index.

## Held-Out Decision Gate

Evaluate both model seeds on the frozen 64 held-out states using the complete held-out target table.

For each state compare:

```text
q_floor(model-selected action) - q_floor(expert-selected action)
```

The validation-selected model passes the held-out gate only if all hold:

1. aggregate mean paired delta > 0;
2. median paired delta >= 0;
3. at least 3 of 4 family mean deltas >= 0;
4. a 10,000-resample family-stratified paired bootstrap has 95% lower confidence bound for mean delta > 0;
5. the non-selected model seed has aggregate mean paired delta >= 0;
6. zero identity/schema/restore/legal-action/fallback violations.

Bootstrap seed: `86086`. Sampling unit is the source state; each replicate resamples 16 states with replacement within each family and then averages across all 64 resampled states.

If valid evidence fails this gate, stop before fresh complete-run evaluation and classify `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`.

## Conditional Fresh Matched A20 Evaluation

Run only if the held-out gate passes.

Use exact fresh standard-start A20 source-run seeds:

`861001..861256`

Run two matched arms on every seed:

1. `expert_non_combat_v1`
2. validation-selected learned policy on the four supported families, with explicit `expert_non_combat_v1` fallback elsewhere.

Both arms use identical frozen Battle Search v2@100, action space, simulator/native identity, max outer steps `500`, and deterministic policy/RNG mapping. Source-run seed and Non-Combat policy RNG must be recorded separately; no CLI default may silently derive one from the other.

No assistance, constructed starts, learned Battle guidance, root-prior variant, restart privilege, extra run, or post-hoc seed replacement is allowed.

Required per-run evidence includes terminal floor/status, reached Act, Boss/later-act/Heart reachability, visible terminal resources, learned decision count, fallback count by family, learned/expert disagreement, simulator/search cost, wall clock, truncation, and controller failure.

### Fresh-run support gate

Across the 256 learned-arm runs require:

- at least 128 valid learned-controlled decisions total;
- at least 32 learned-controlled decisions in each of `MAP_SCREEN` and `REWARDS`;
- at least one learned-controlled decision in both `REST_ROOM` and `TREASURE_ROOM`;
- zero supported-screen inference failure routed silently to expert fallback.

If all run identities are valid but this natural occupancy support is not met, classify `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`; do not add runs or expand learned screen scope.

## Fresh-Run Primary Metric

Primary metric:

```text
paired terminal_floor delta = learned - expert
```

Use 10,000 paired bootstrap resamples of the 256 source-run seeds with replacement, seed `861086`, and report the 2.5th/97.5th percentiles of mean paired terminal-floor delta.

Secondary descriptive metrics:

- Act-2+, Act-3+, Act-4/Heart reachability counts;
- complete-run wins if any;
- mean/median floor delta;
- learned-control coverage;
- supported-family disagreement rates;
- resource/cost diagnostics.

Secondary metrics cannot rescue a failed primary classification.

## Terminal Classification

Emit exactly one terminal classification.

### `NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED`

Require:

1. all artifact/integrity gates pass;
2. held-out decision gate passes;
3. fresh-run support gate passes;
4. fresh-run 95% bootstrap lower bound for mean terminal-floor delta > 0;
5. learned arm has no more invalid/truncated/controller-failure runs than expert;
6. learned arm reaches Act 2+ on at least as many matched seeds as expert.

### `NON_COMBAT_POLICY_HARM_CONFIRMED`

Require valid support and fresh-run 95% bootstrap upper bound for mean terminal-floor delta < 0.

### `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`

Valid experiment that is neither established improvement nor confirmed harm. A valid held-out-gate failure enters this class without running the conditional fresh evaluation.

### `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`

All integrity/training/held-out prerequisites needed to reach fresh evaluation are valid, but the exact 256-run learned-control support gate is unmet.

### `INCOMPLETE`

Identity/provenance/restore/public-context/legal-action/schema/target/checkpoint/execution/retention failure, or any missing required evidence.

## Required Artifacts

Retain and hash at minimum:

1. input eligibility report resolving T065/T075/T078/T081/T085 and current native identity;
2. 320-state current-native revalidation report;
3. complete counterfactual target manifest/table with exact state/action/seed linkage;
4. training normalizers, batch plans, both checkpoints, and training reports;
5. validation checkpoint-selection report frozen before held-out evaluation;
6. held-out paired action-value report and bootstrap;
7. conditional 256-seed fresh-run source/arm manifests and outcomes;
8. fresh-run bootstrap/classification report;
9. terminal report;
10. retention manifest with hashes, sizes, regeneration commands, compatibility requirements, and deletion conditions.

Formal simulator stages must follow the repository detached-job/resource-admission conventions and record effective worker/shard execution. Bounded smoke/canary execution is operational only and cannot substitute for formal artifacts.

## Out Of Scope

- any Battle model, Battle prior/value repair, root-prior allocation, Search@400/1600 comparison, or Battle search semantic change;
- T066 joint/alternating learning;
- new Non-Combat input schema or architecture sweep;
- imitation of `expert_non_combat_v1`;
- human trajectories, human labels, human card/deck rankings, or manual strategy targets;
- SHOP/EVENT/CARD_SELECT/BOSS_RELIC learned control;
- hidden-future sampler work under T034;
- complete-run scale-up beyond the exact conditional 256 matched seeds;
- live CommunicationMod promotion.

## Acceptance Criteria

1. Exact T075 cohort reuse and current-native 320/320 revalidation pass with no replacement.
2. Battle remains exactly unguided Search v2@100/highest_mean with no policy/value callback.
3. Counterfactual targets are complete for every eligible action and frozen continuation seed.
4. Deployable inputs satisfy the exact public `non-combat-model-input-v1` contract.
5. Two frozen model seeds train exactly as specified; validation-only checkpoint selection is auditable.
6. Held-out comparison and bootstrap are complete and replayable.
7. Conditional fresh evaluation, if unlocked, uses exactly 256 matched seeds/two arms and the frozen support/statistics contract.
8. Exactly one terminal class is produced from retained evidence.
9. Final task/result/lifecycle documentation on the same PR head states the narrow claim boundary and successor disposition.

## Successor Boundary

A valid T086 result closes this exact minimal Non-Combat round.

- If `NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED`, the learned Non-Combat checkpoint may become the frozen Non-Combat side of a later separately published alternating/joint task. This does **not** automatically activate T066.
- If harm or improvement-not-established, do not tune T086 hyperparameters or add screen families inside this task. Planner must first inspect failure mechanism before publishing another Non-Combat variant.
- Regardless of result, T085 learned Battle value remains closed. Reopening learned Battle requires a separate task with a new mechanism hypothesis.