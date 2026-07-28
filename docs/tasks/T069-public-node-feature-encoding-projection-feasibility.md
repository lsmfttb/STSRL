# T069: Public-Node Feature-Encoding Projection Feasibility

## Objective

Determine whether the dominant Search v2 checkpoint feature-encoding cost can
be removed by encoding the invariant public run context once per battle-search
scope and reusing that exact current-schema projection at every public node.

This is a bounded feasibility task. It must either:

- prove the proposed projection is exact, implement one explicit
  search-scope projection boundary, preserve accepted T067/T068 semantics, and
  re-enter the 16-record cost calibration; or
- prove the projection is not exact or cannot make every required guided arm
  compute-feasible, then close this direction with one evidence-based
  recommendation.

T069 does not run the 93-record outcome comparison and cannot promote a
controller.

## Current Main Baseline

T068 is accepted on `main` at merge commit
`e70d047cdeb406ca223031460ef134201030a4de`; its exact artifact-producing
implementation commit is
`3dd14e31bbe310fef0b86d3fecf9ef203e67a411`. T068 preserved the accepted
T067 controller semantics while tracing every callback on retained T052
records `0:16`.

The pinned native callback consumes every Python response synchronously before
traversal continues. T068 therefore observed only singleton batches:

| Arm | Requests | Exact batches >=2 | Singleton fallbacks |
|---|---:|---:|---:|
| `prior_only` | 207 | 0 | 207 |
| `value_only` | 261 | 0 | 261 |
| `prior_value` | 398 | 0 | 398 |

Native-boundary batching is closed. No calibration, 93-record outcome
comparison, or promotion was authorized.

The same audit measured checkpoint feature encoding as the dominant separable
inference component:

| Arm | Feature encoding ms | Forward-pass ms | Model calls |
|---|---:|---:|---:|
| `prior_only` | 46012.216903999724 | 5298.554254999942 | 207 |
| `value_only` | 48498.62396400033 | 4038.125492999143 | 261 |
| `prior_value` | 63462.21188099877 | 2507.4573129997475 | 398 |

`TorchPolicyValueCheckpointScorer.score_decision_context` currently encodes
`context.public_run_context` for every callback even though Search v2 builds
each node context from the same root public run context. T069 must prove that
invariance and exact-vector reuse before changing this path; it must not assume
that measured component time is wholly removable.

This remains `full_simulator_state_oracle_like` cost-feasibility evidence only.
It is not fixed-cohort outcome evidence, natural A20 performance,
normal-information strength, live-game validation, broad-training evidence, or
final-agent evidence.

## Dependencies

- accepted T068 callback-dependency, feasibility, semantic, decision, stage,
  and retention evidence;
- accepted T067 Search v2 cost attribution and calibration contracts;
- accepted T062 Search v2 controller and four-arm meanings;
- retained T052 fixed Boss/later-act cohort;
- retained T043 public policy/value checkpoint;
- manifest-pinned `sts_lightspeed` integration.

## Inputs And Artifacts

The stable T068 artifact root is
`artifacts/t068-native-boundary-batched-inference-feasibility/reproduction-3dd14e3/`.
T069 consumes the exact T068 retention manifest:

| Artifact | Schema | Bytes | SHA-256 |
|---|---|---:|---|
| `t068-retention-manifest.json` | `t068-native-boundary-retention-manifest-v1` | 65390 | `bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678` |

The manifest indexes 97 artifacts totaling 4,598,645 bytes and records the
exact T067 manifest, T052 cohort, T043 checkpoint, T061 retention contract,
native commit `3cb9ebecb87c38044b34aa0e013d42b222a04087`, source verification,
callback traces, component costs, semantic comparison, stage layout, and
regeneration commands. T069 must verify those identities before business logic
runs.

Generated outputs remain under the stable ignored root
`artifacts/t069-public-node-feature-encoding-projection-feasibility/`. Retain
compact attribution, invariance, projection, semantic, calibration, decision,
stage-execution, and retention reports with exact hashes, sizes, input
identities, worker/shard layouts, wall-clock costs, regeneration commands, and
deletion conditions. Large traces stay out of Git.

## Scope

### 1. Exact feature-encoding attribution and invariance audit

On retained T052 record `0:1` and deterministic records `0:16`, instrument the
accepted unprojected T068 behavior for `prior_only`, `value_only`, and
`prior_value`. Separate at least:

- public run-context validation and encoding;
- snapshot-feature validation/copy or transformation;
- legal-action feature validation/copy or transformation;
- final state-vector assembly;
- tensor construction, model forward, result postprocessing, callback total,
  native search time, and total wall time.

For every callback, publish an occurrence-safe request id; complete current
feature schema ids, versions, names, and sizes; canonical public-run-context
identity; encoded-vector hash; snapshot and ordered action-feature hashes; and
component timings.

The audit must prove, rather than assume, that every callback within one search
scope uses the same complete public run context and that encoding it once
produces the exact float vector required by the accepted T043 checkpoint.
Missing context, mutable context, a schema mismatch, non-finite features, or an
unexplained hash change fails closed.

### 2. Bounded projection feasibility gate

Build an executable, diagnostic-only prototype that accepts an explicit
current-schema encoded public-context projection while leaving snapshot and
ordered legal-action features request-local.

Before production integration, publish a deterministic gate requiring:

- exact projected and unprojected public-context vectors for every audited
  request;
- identical complete scorer inputs and outputs within the published `1e-6`
  policy/value tolerance;
- exact selected action, traversal, simulator-step, chance/RNG, and terminal
  semantics on record `0:1`;
- measured projected component costs on `0:16`, not a subtraction-only
  estimate;
- a conservative projection showing both T067/T068-infeasible arms can reach
  the 1.10 minimum-budget wall-clock ceiling.

If any condition fails, do not integrate the projection and do not run
calibration. Emit a versioned infeasibility report and proceed directly to the
decision stage.

### 3. One search-scope projection boundary

Only if the feasibility gate passes, implement exactly one versioned boundary
that prepares the complete public-context feature vector once when a Search v2
battle decision begins and supplies it explicitly to every scorer invocation
in that search scope.

The projection is local to one battle-search decision. It must not be a global,
cross-battle, cross-run, process-lifetime, object-identity, or digest-only
cache. Its key and provenance include the complete canonical public context
plus current schema id, version, names, size, dtype, device, checkpoint
identity, and projection implementation version. The scorer must remain able
to execute the accepted unprojected path.

Projection construction, lookup, validation, vector assembly, tensor
construction, model forward, postprocessing, callback, native-search, and
total wall time remain separately reported. Invalid, stale, partial,
reordered, duplicate, or mismatched projection inputs fail closed.

### 4. Semantic equivalence

Compare accepted unprojected T068 behavior with the diagnostic prototype and,
when implemented, the projected controller.

On frozen public-node/action fixtures and retained T052 record `0:1`:

- complete scorer input vectors are exactly equal;
- policy probabilities, leaf values, terminal HP, and structured resource
  outputs match within `1e-6`;
- selected occurrence-safe action identities match exactly;
- request identities and order, native traversal/expansion, root rows,
  simulator steps, chance/RNG behavior, and terminal battle fields match
  exactly;
- every request has one response and no hidden simulator field enters model
  input.

Timing fields are excluded from byte equality but remain separately reported.

### 5. Conditional calibration re-entry

Only after the feasibility and semantic gates pass, rerun cost-only calibration
on deterministic T052 indices `0:16` with 16 explicit one-record shards and 16
effective workers, using the exact T068 Python/native ABI pairing and host.

Baseline remains native budget 100. Guided arms start at budget 1 and use the
unchanged deterministic T067 candidate sequence. The simulator-step family
must match baseline aggregate native simulator steps within 5%; the wall-clock
family must match baseline aggregate wall-clock seconds within 10%.

Run explicit unprojected/projected paired cost measurement under the same stage
layout. Report component timings, model calls, simulator steps, wall time,
projection construction and reuse counts, failures, and provenance per arm.

If any required guided arm exceeds the 1.10 wall ceiling at budget 1, record
minimum-budget infeasibility and stop. Otherwise continue the predeclared
candidate sequence until all simulator-step and wall-clock locks succeed or one
is proven infeasible.

Do not run or synthesize the 93-record outcome comparison in T069.

### 6. Decision

Recommend exactly one next task:

- a separately published Search v2 fixed-cohort comparison re-entry only if all
  required calibration locks succeed; or
- closure of public-feature projection and one narrowly named alternative
  derived from the new measured dominant remaining cost.

## Out Of Scope

- Native callback batching, speculative/asynchronous expansion, or tree-policy
  changes.
- The T052 93-record outcome comparison or controller promotion.
- Changing or retraining the T043 checkpoint, model architecture, feature
  schemas, feature values, dtype, output meanings, or action ordering.
- Cross-battle or process-global feature caching.
- Hidden simulator inputs, hidden RNG state, draw order, future encounters, or
  the hidden Act-3 second Boss.
- Complete-run source generation, natural A20 scale-up, broad training,
  normal-information promotion, live-game claims, or final-agent claims.
- A second unrelated performance repair.

## Design Constraints

- The controller remains `full_simulator_state_oracle_like`; model inputs
  remain the published public state/context only.
- The accepted T068 unprojected path remains explicitly constructible.
- The projection must contain the complete current-schema public-context vector
  and must never guess missing provenance.
- Snapshot and ordered legal-action features remain request-local unless the
  exact audit separately proves an identical immutable component; T069 may not
  widen scope to a second optimization.
- The pinned `sts_lightspeed` integration remains simulator authority and the
  real game remains mechanics authority.
- Every substantial WSL attribution, prototype, and calibration stage uses 16
  shards/workers by default. The one-record semantic smoke may use one worker
  with that reason recorded.
- No favorable arm may substitute for another required arm.

## Deliverables

- Versioned feature-component attribution and public-context invariance report.
- Deterministic occurrence-safe feature identity records for every guided arm.
- One executable diagnostic projection prototype or explicit proof that exact
  projection is unavailable.
- If the feasibility gate passes, one versioned search-scope projection
  boundary with focused scorer/controller tests.
- Paired semantic-equivalence report.
- Conditional 16-record calibration and cost reports.
- Versioned decision, stage-execution, and stable retention manifests.
- Exactly one next recommendation.
- Documentation impact report; authoritative planner documents remain
  maintainer-owned.

## Acceptance Criteria

- Every T068/T067/T052/T043/T061/native input matches its published identity.
- All three guided arms have complete feature-component attribution and no
  unreported request, response, failure, or schema mismatch.
- Public-context invariance and vector equality are evaluated from complete
  canonical inputs, not object identity or a partial/digest-only key.
- The feasibility gate is evaluated exactly as published. A failed gate exits
  before production integration or calibration.
- Any implemented projection is local to one search scope, validates complete
  current-schema provenance, and preserves every required input and search
  semantic.
- Projected outputs match within `1e-6`; input vectors, identities, traversal,
  simulator steps, RNG behavior, and terminal fields match exactly on the
  semantic gate.
- Conditional calibration uses the same 16 source identities, 16
  shards/workers, deterministic candidates, and original 5%/10% tolerances.
- T069 runs no 93-record outcome aggregation and makes no promotion, natural
  A20, normal-information, live-game, broad-training, or final-agent claim.
- Exactly one next task is recommended from the published decision rule.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused
T062/T067/T068/T069 tests, task-document checks, and `git diff --check`.

Before WSL evidence, verify or regenerate the exact T068 inputs through its
retention-manifest commands and run the pinned-source verifier. Run attribution,
prototype, semantic, and any calibration gates through WSL with the exact
PyTorch/native ABI pairing. The PR must report commands, source and checkpoint
identities, feature schemas and hashes, record ranges, workers, shards,
component timings, model calls, simulator steps, wall time, reuse counts,
failures, and the conservative feasibility decision.

Missing inputs, changing context, a vector mismatch, unavailable projection, or
a failed cost gate must produce an explicit report and non-ambiguous decision
rather than a draft claim that the task cannot proceed.

## Legacy Reference

Consult accepted T062, T067, and T068 code/evidence plus the T033 public-context
encoder, T043 checkpoint scorer, and T052 retained cohort. Reuse current
validation, cost-attribution, semantic, and retention surfaces selectively.
Closed exact-node caching and native batching are diagnostic evidence, not
implementation paths for T069.

## PR Report

Report task ID, consumed identities, exact code/native commits, component
attribution, invariance and feasibility gates, projection boundary if
implemented, semantic evidence, every calibration candidate if authorized,
feature/reuse/cost telemetry, failures, verification, limitations,
documentation impact, and the single next recommendation.
