# T068: Native-Boundary Batched Inference Feasibility

## Objective

Determine whether public-node policy/value inference can be batched across the
native/Python Search v2 callback boundary without changing search semantics,
then measure whether that one boundary change can make all required T067
calibration arms compute-feasible.

This is a bounded feasibility task. It must either:

- prove a semantics-preserving batch opportunity, implement exactly one
  request/response batch boundary, and re-enter the T067 cost calibration; or
- prove that the current native traversal exposes no useful exact batch, or
  that the bounded batch cannot satisfy the cost gate, and close this direction
  with one evidence-based recommendation.

T068 does not run the 93-record outcome comparison and cannot promote a
controller.

## Current Main Baseline

T067 is accepted on `main` at merge commit
`c65786e614d05c562eb78afaa61dbacff2f8f5bb`. Its exact implementation commit is
`ea47ee9df57b026bff96cf5c902f6a207b534cb1`, and its repaired controller is
`battle_search_v2_oracle_like_t067_cache_v1` under the
`full_simulator_state_oracle_like` information regime.

T067 implemented a process-local, one-search-scope exact public-node inference
cache while preserving the T062 checkpoint, tree policy, leaf boundary,
chance/RNG behavior, root rule, legal-action ordering, and four-arm meanings.
On the accepted T052 `0:16` calibration range, the cache recorded 866 lookups,
0 hits, 866 misses, and 0 evictions. The retained attribution reports these
aggregate guided-arm costs:

| Arm | Model calls | Feature encoding ms | Forward-pass ms | Budget-1 wall ratio |
|---|---:|---:|---:|---:|
| `prior_only` | 207 | 42594.21366400068 | 4067.020533000118 | 1.164582194439893 |
| `value_only` | 261 | 47340.60153700284 | 4143.453005998936 | 1.1487986693454382 |
| `prior_value` | 398 | 61501.05700400218 | 3165.177669999366 | 1.0240645131300026 |

`prior_only` and `value_only` exceed the T062/T067 wall-clock ceiling of 1.10
at the minimum legal integer budget 1. T067 therefore failed all required
locks, correctly ran no 93-record comparison, made no outcome or promotion
claim, closed exact-cache repair, and selected exactly
`T068-native-boundary-batched-inference-feasibility`.

This is accepted cost-feasibility evidence only. It is not normal-information
strength, natural A20 performance, live-game validation, broad-training
evidence, or final-agent evidence.

## Dependencies

- accepted T067 cost attribution, semantic-equivalence, calibration, decision,
  and retention evidence;
- accepted T062 Search v2 controller and native tree-internal callback surface;
- the retained T052 93-record Boss/later-act cohort;
- the retained T043 diagnostic public policy/value checkpoint;
- the manifest-pinned `sts_lightspeed` integration line.

## Inputs And Artifacts

The stable T067 artifact root is
`artifacts/t067-battle-search-v2-inference-cost-repair/reproduction-ea47ee9/`.
T068 consumes these exact artifacts:

| Artifact | Schema | Bytes | SHA-256 |
|---|---|---:|---|
| `t067-stage-execution.json` | `t067-battle-search-v2-stage-execution-v1` | 36640 | `2212b4f763183dad514b04aba13d6af236a7c89431ca0cdb6292e34ba400160b` |
| `t067-semantic-equivalence.json` | `t067-battle-search-v2-semantic-equivalence-v1` | 1683 | `6307e0685a6d18231113949b5663c7f8afe6d11a6cbb5398f412d913d38426b7` |
| `t067-budget-1-raw-merged.json` | `t062-battle-search-v2-comparison-v1` | 24038069 | `c9b4f2f8a5d340c08a423a8f3deb399ef0248cb505e11068ecf82da3d6559aca` |
| `t067-cost-attribution.json` | `t067-battle-search-v2-cost-comparison-v1` | 25272885 | `50f16d42fd2496446107b01e039fa98b9a7de7877ed81e69131312e4a998fc2f` |
| `t067-calibration-manifest.json` | `t067-battle-search-v2-calibration-v1` | 4473 | `775766391a28e26d11d14db8a6a7f535a8b69994ed491cdd075d665daaa0288b` |
| `t067-decision-report.json` | `t067-battle-search-v2-decision-v1` | 1003 | `e8fa984ee1e0a8c23080b5d1ccedf4e734e4b33c1924d4e108c4604c1c107265` |
| `t067-retention-manifest.json` | `t067-battle-search-v2-retention-manifest-v2` | 43659 | `2119e36bccff86fd65f00474177d11bb222a05303651dc18423de7f1174d35da` |

The T067 manifest indexes 72 artifacts totaling 77,759,244 bytes. Its six
authoritative regeneration commands prepare an exact detached source checkout,
run the pinned verifier, semantic smoke, 16-worker calibration, deterministic
merge, and recursive finalization without depending on a disposable worktree
or overwriting accepted evidence. Those commands are the authoritative input
regeneration path for T068.

The native baseline remains repository `lsmfttb/sts_lightspeed`, ref
`stsrl/main`, commit `3cb9ebecb87c38044b34aa0e013d42b222a04087`. The source
manifest and verifier identities are inherited through the T067 retention
manifest. Any T068 native change must name its exact fork commit, update the
source manifest and verifier capability assertions, and preserve the accepted
baseline as reproducible provenance.

The T052 cohort and T043 checkpoint remain the exact identities recorded by
T067. T068 must resolve them through the T067 retention contract rather than a
temporary worktree or undocumented copy.

Generated outputs remain under the stable ignored root
`artifacts/t068-native-boundary-batched-inference-feasibility/`. Retain compact
reports and a manifest with exact hashes, sizes, source/checkpoint/cohort
identities, request traces, batch layouts, worker/shard layouts, wall-clock
costs, regeneration commands, and deletion conditions. Large traces stay out
of Git.

## Scope

### 1. Exact callback-dependency audit

Instrument the accepted unbatched T067 behavior on the retained semantic smoke
record `0:1` and calibration records `0:16`. For `prior_only`, `value_only`,
and `prior_value`, record:

- every public-node inference request with a stable occurrence-safe request id;
- ordered legal-action identities and the complete published public input
  identity;
- whether policy, value, or both outputs are required;
- the native traversal point that produces the request;
- the earliest point at which its result is consumed;
- explicit dependency edges between request completion and subsequent native
  selection, expansion, chance, or backup work;
- singleton and candidate batch sizes, flush reasons, and timing.

A valid batch contains at least two requests that are simultaneously ready
before any member result is consumed. Speculative expansion, reordered tree
selection, delayed backups that change later selection, cross-simulator state
reuse, or hidden-state model inputs are not valid batching.

The audit must publish a deterministic feasibility gate before production
implementation:

- every guided arm has at least one exact batch of size two or greater on the
  retained `0:16` range;
- the proposed batch boundary keeps request content and native dependency order
  exact;
- an executable prototype or microbenchmark reports measured batch-size
  distribution and component costs;
- a conservative projection states whether both T067-infeasible arms could
  reach the 1.10 minimum-budget wall ceiling.

If this gate fails, do not invent a batch, change the search algorithm, or run
calibration. Emit a versioned infeasibility report and proceed directly to the
decision stage.

### 2. One native/Python batch boundary

Only if the feasibility gate passes, implement exactly one versioned
request/response batch surface between native Search v2 and the existing public
checkpoint scorer.

The change may batch feature packing, tensor construction, and model forward
execution for the audited ready requests. It must not change:

- checkpoint bytes, model architecture, public feature schemas, or output
  meanings;
- legal-action identity or order;
- native tree policy, expansion order, leaf-value boundary, backup semantics,
  chance/RNG consumption, root selection, or search budgets;
- the meanings of baseline, `prior_only`, `value_only`, and `prior_value`;
- controller information regime or provenance.

Batch capacity, readiness rule, flush rule, singleton fallback, device, dtype,
PyTorch thread/process settings, and native source identity are versioned
behavioral provenance. Invalid batch shapes, incomplete requests, reordered
responses, duplicate/missing request ids, or output mismatches fail closed.

### 3. Semantic equivalence

Compare accepted unbatched T067 behavior with the feasibility prototype and,
when implemented, the batched controller.

On frozen public-node/action fixtures and retained T052 record `0:1`:

- policy probabilities, leaf values, and structured outputs match within
  `1e-6`;
- selected occurrence-safe legal-action identities match exactly;
- native request identities, traversal/expansion order, root rows, simulator
  steps, chance/RNG behavior, and terminal battle fields match exactly;
- every request receives exactly one response and no hidden simulator field
  enters model input.

Timing fields are excluded from byte equality but remain separately reported.

### 4. Conditional calibration re-entry

Only after the feasibility and semantic gates pass, rerun cost-only calibration
on deterministic T052 indices `0:16` with 16 explicit one-record shards and 16
effective workers, using the exact T067 Python/native ABI pairing and the same
host.

Baseline remains native budget 100. Guided arms start at budget 1 and use the
unchanged deterministic T067 candidate sequence. The simulator-step family
must match baseline aggregate native simulator steps within 5%; the wall-clock
family must match baseline aggregate wall-clock seconds within 10%.

Run an explicit unbatched/batched cost comparison under the same stage layout
before accepting a speedup. Report request count, realized batch-size
distribution, singleton fallbacks, feature/tensor/forward/callback time, native
simulator steps, model calls, wall time, and failures per arm.

If any required guided arm exceeds the 1.10 wall ceiling at budget 1, record
minimum-budget infeasibility and stop. If all minimum-budget wall gates are
feasible, continue the predeclared candidate sequence until every
simulator-step and wall-clock lock succeeds or one is proven infeasible.

Do not run or synthesize the 93-record outcome comparison in T068.

### 5. Decision

Recommend exactly one next task:

- a separately published Search v2 fixed-cohort comparison re-entry only if all
  required T067 calibration locks succeed; or
- closure of native-boundary batching and one narrowly named alternative
  derived from the measured dominant remaining cost when feasibility or
  calibration fails.

## Out Of Scope

- The T052 93-record outcome comparison or controller promotion.
- Changing or retraining the T043 checkpoint.
- Changing feature schemas, model architecture, tree policy, leaf semantics,
  RNG behavior, root selection, action ordering, or required ablation meanings.
- Speculative or asynchronous tree expansion that changes native traversal.
- Cross-battle training, complete-run source generation, or natural A20
  scale-up.
- Root-only or post-search guidance substitutions.
- Public-consistent hidden-future sampling, normal-information promotion,
  live-game claims, broad training, or final-agent claims.
- A second unrelated performance repair.

## Design Constraints

- The controller remains `full_simulator_state_oracle_like`.
- Model inputs remain the published public state/context only.
- The real game remains mechanics authority and the pinned `sts_lightspeed`
  integration remains simulator authority.
- T067 unbatched behavior remains explicitly constructible for paired
  diagnostics.
- Batching is legal only across proven simultaneously ready requests.
- Output demultiplexing uses exact request ids and occurrence-safe ordered legal
  actions; positional guessing fails closed.
- Monotonic timing telemetry stays separate from outcome data.
- Every substantial WSL trace, prototype, and calibration stage uses 16
  shards/workers by default. A lower count requires a stage-specific resource
  or tooling reason. The one-record semantic smoke may use one worker with that
  reason recorded.
- No favorable arm may substitute for another required arm.

## Deliverables

- Versioned callback-dependency and batch-feasibility report.
- Deterministic request trace and compact batch-opportunity summary for all
  guided arms.
- One bounded batch prototype or an explicit proof that exact batching is
  unavailable.
- If the feasibility gate passes, one versioned native/Python batch boundary,
  focused native/Python tests, updated source manifest/verifier, and paired
  semantic report.
- Conditional 16-record calibration reports and locked or fail-closed
  calibration manifest.
- Versioned decision report, stable retention manifest, and exactly one next
  recommendation.
- Documentation impact report; authoritative planner documents remain
  maintainer-owned.

## Acceptance Criteria

- Every consumed T067/T052/T043/native artifact matches its published identity.
- All three guided arms have complete request/dependency traces with no
  unreported request, response, or failure.
- The feasibility gate is evaluated exactly as published. A failed gate exits
  before production integration or calibration.
- Any implemented batch contains only simultaneously ready requests and
  preserves every required semantic field and selected action.
- Batched policy/value outputs match accepted T067 within `1e-6`; identities,
  traversal order, simulator steps, RNG behavior, and terminal fields match
  exactly on the semantic gate.
- Conditional calibration uses the same 16 source identities, 16
  shards/workers, deterministic candidate sequence, and original 5%/10%
  tolerances.
- T068 runs no 93-record outcome aggregation and makes no controller-promotion,
  natural-A20, normal-information, live-game, broad-training, or final-agent
  claim.
- Exactly one next task is recommended from the published decision rule.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T062/T067/T068
tests, task-document checks, and `git diff --check`.

Before WSL evidence, regenerate or verify the T067 inputs through the exact
retention-manifest commands and run the pinned-source verifier. Run the
dependency audit and any prototype/calibration through WSL with the exact
PyTorch/native ABI pairing. The PR must report commands, native source
identity, request/dependency counts, batch-size distribution, record ranges,
workers, shards, component timings, model calls, simulator steps, wall time,
fallbacks, and failures for every stage.

If native integration changes, clean-build its exact commit and exercise both
the accepted unbatched T067 boundary and the T068 batch capability. Missing
inputs, an unavailable batch opportunity, or a failed gate must produce an
explicit report and non-ambiguous decision rather than a draft claim that the
task cannot proceed.

## Legacy Reference

Consult accepted T062 and T067 code/evidence plus T025--T029, T035, T043, and
T046--T061. Reuse the T067 attribution, calibration, semantic, and retention
surfaces selectively. Old root-only guidance and closed cache/allocation
repairs are diagnostic evidence, not the T068 implementation.

## PR Report

Report task ID, consumed identities, exact native commit, callback dependency
audit, feasibility-gate result, prototype or implementation boundary,
semantic-equivalence evidence, every calibration candidate if authorized,
request/batch/cost telemetry, failures, verification, limitations,
documentation impact, and the single next recommendation.
