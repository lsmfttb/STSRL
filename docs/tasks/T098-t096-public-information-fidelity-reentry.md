# T098: T096 Public-Information Fidelity Re-entry

Artifact Eligibility Required: false

## Objective

Re-enter the exact scientific fidelity gate that caused T096 to terminate
`NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`, using the now-accepted native
source capability from T097.

T098 is a **focused fidelity re-entry**, not a repeat of the full T096 pilot and
not a particle-count convergence task.

The accepted native source is fixed at:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d309170198e21e57041a84dcfdbc255cdda4052e`

The scientific question is:

> does the repaired native current-player-information projection now support the
> required draw-knowledge and hidden-intent visibility semantics without
> regressing the already-passing ordinary hidden-draw sampler boundary?

A successful T098 closes only the **T096 native visibility/fidelity blocker**.
It does not establish particle-count sufficiency, Search improvement, model
quality, controller improvement, or T034 completion.

## Publication Baseline

Publication base:

`main @ 625c25ab9b28cf965c678ee2e8fa66f7235f402f`

Relevant accepted lineage:

- T096: ordinary hidden-draw pilot passed public/legal parity, hidden diversity,
  and bounded next-card TV, but terminated
  `NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`;
- native issue `lsmfttb/sts_lightspeed#17` and PR #18 repaired current
  player-information fidelity;
- T097 accepted exact native source
  `d309170198e21e57041a84dcfdbc255cdda4052e` with terminal
  `NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED`.

T098 must consume the T097 exact source manifest unchanged. A native source
change is outside scope and blocks this task pending a separate native workflow.

## Research Boundary

The object remains the current player information state:

```text
full native Battle state S_t
        |
        | game visibility + remembered current knowledge
        v
public information state I_t
```

A supported particle remains valid only when:

```text
public_information_projection(S'_t) == public_information_projection(S_t)
```

and ordered public legal-action identities are exactly equal.

Normal play remains no-SL/no-PRNG-cracking. Hidden deterministic RNG internals
must not enter public features or be reverse engineered for this task.

## Required Fidelity Families

T098 must produce bounded, deterministic evidence for all four families below.

### A. Ordinary hidden draw / visible intent regression

Use at least one ordinary Battle player-decision anchor satisfying the existing
T096 ordinary-information boundary:

- draw order classified `hidden`;
- enemy intent classified `public_exact`;
- projection fidelity `supported`;
- bounded particle sampling succeeds;
- every accepted particle has exact public-projection parity;
- every accepted particle has exact ordered-public-legal-action parity;
- at least two future-dynamics-relevant hidden realizations are observed.

This is a regression gate only. T098 must not rerun the formal T096 4×8192
distribution experiment.

### B. Supported draw-knowledge state

Demonstrate at least one native-supported state where the player knows more than
ordinary hidden draw order and the sampler still remains valid.

A Headbutt/Rebound-style exact known-top state is the preferred primary witness.

Required properties:

- projection is `supported`;
- draw-order classification is `known_prefix` or another exact supported
  known-position classification;
- the known card/position is identical across accepted particles;
- unconstrained hidden remainder can still vary when non-empty;
- public projection and ordered public legal actions remain exactly equal.

Forethought-style exact-position evidence may be used as additional evidence but
is not required if the primary witness already satisfies the contract.

### C. Frozen Eye exact-order visibility

Demonstrate one native-supported Frozen Eye state.

Required properties:

- draw-order classification is `full_public_exact`;
- visible order is complete and exact;
- bounded particle sampling must not alter that order;
- public projection and ordered legal actions remain exactly equal;
- no hidden draw-order diversity may be claimed when the order is public.

This is a visibility correctness test, not a diversity requirement.

### D. Runic Dome hidden intent

Demonstrate one native-supported Runic Dome state whose monster state is not a
known timing-mixed unsupported counter case.

Required properties:

- current intent is classified `hidden`;
- current move / attack category / current-intent damage fields are absent from
  the public projection;
- previously observed move/history and visible public statuses remain retained;
- projection fidelity is `supported`;
- bounded particle sampling succeeds;
- every accepted particle preserves exact public projection and ordered legal
  actions.

Use a monster/state for which native semantic timing is representable under the
accepted T097 capability.

## Intentional Unsupported Cases Are Not Failures

T098 must separately verify at least one accepted fail-closed case for state that
the native capability intentionally cannot represent exactly, such as a
Runic-Dome timing-mixed monster counter.

For such a case:

- public projection must be `unsupported_fidelity`;
- raw/misleading semantic hidden-roll value must not leak;
- the sampler must reject the anchor.

Correct fail-closed behavior satisfies this check. T098 must not require every
monster/mechanic to become supported and must not reinterpret conservative
unsupported states as a failure of the repaired architecture.

## Evidence Source

The native deterministic `StepSimulator.t096_visibility_audit()` may be used as
authoritative mechanics-level evidence for supported/unsupported transition
properties.

However, T098 must also exercise the actual public projection and sampler API on
bounded runtime anchor(s), rather than concluding solely from audit booleans.

Implementation may add a small STSRL-side report/command/helper that consumes the
native APIs. Python must not recreate Slay the Spire hidden mechanics or directly
patch private native fields.

## Frozen Bounded Sampling Budget

This task is about semantic fidelity, not Monte Carlo convergence.

For every supported runtime witness that invokes the sampler, use a fixed
bounded particle count:

`N = 32`

unless the implementation demonstrates that fewer particles are sufficient for a
pure deterministic invariant. Any alternate count must remain <= 64 and be
reported.

No accepted result may infer particle-count sufficiency from this budget.

## Required Report

Produce one versioned focused report, for example:

`t098-public-information-fidelity-reentry-v1`

The report must include:

- exact STSRL implementation/evidence head;
- exact native source repository/ref/commit;
- public-information projection schema;
- native visibility-audit schema;
- witness identity/provenance for families A-D;
- particle count used for each sampled witness;
- public-projection parity counts;
- ordered-public-legal-action parity counts;
- hidden-diversity result where hidden diversity is semantically expected;
- exact draw-knowledge classification and preserved fact(s);
- Frozen Eye exact-order result;
- Runic Dome hidden-intent result;
- intentional unsupported/fail-closed result;
- whether any private field leaked;
- terminal classification.

No large retained artifact is required. A compact JSON report under the normal
ignored artifact path is sufficient if the command and schema are documented.

## Acceptance Criteria

T098 passes only if:

1. exact native source remains
   `d309170198e21e57041a84dcfdbc255cdda4052e`;
2. ordinary hidden-draw / visible-intent regression passes;
3. at least one supported draw-knowledge witness passes;
4. Frozen Eye exact-order visibility passes;
5. at least one supported Runic Dome hidden-intent witness passes;
6. at least one intentional mixed/unsupported witness fails closed correctly;
7. every supported sampled witness has exact public-projection parity;
8. every supported sampled witness has exact ordered-public-legal-action parity;
9. hidden diversity is demonstrated where hidden state is still unconstrained;
10. no private RNG/raw hidden storage leaks into the public projection;
11. no Python reconstruction of hidden mechanics is introduced;
12. no formal T096 4×8192 rerun, particle convergence, Search, training,
    controller promotion, T034 closure, Non-Combat work, or T066 work occurs.

## Terminal Classifications

### `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`

Use only if all acceptance criteria pass.

Meaning:

- the native visibility/fidelity condition that terminated T096 is closed on the
  required representative fidelity families;
- the previously accepted ordinary hidden-draw sampler boundary has not
  regressed;
- a separate particle-count convergence task may now be considered.

This terminal does not close T034 or establish an exact posterior.

### `DRAW_KNOWLEDGE_FIDELITY_INSUFFICIENT`

Use if ordinary regression remains valid but the required supported
draw-knowledge or Frozen Eye semantics cannot be validated.

### `INTENT_VISIBILITY_FIDELITY_INSUFFICIENT`

Use if ordinary regression remains valid but the required supported Runic Dome
hidden-intent semantics cannot be validated.

### `PUBLIC_HIDDEN_FUTURE_SAMPLER_REGRESSION`

Use if the previously passing ordinary supported sampler boundary now fails
public parity, legal-action parity, hidden diversity, or leaks private state.

### `FAIL_CLOSED_BOUNDARY_INVALID`

Use if an intentionally unsupported state is silently treated as supported,
leaks hidden timing/private state, or can be sampled as an accepted supported
particle batch.

### `INCOMPLETE`

Use when required witnesses/evidence cannot be produced without changing the
frozen task contract.

No non-success terminal authorizes convergence.

## Explicit Non-Claims

T098 does not establish:

- exact deterministic-seed posterior correctness;
- IID hidden-state samples;
- arbitrary-mid-Battle universal support;
- particle-count sufficiency;
- information-set-optimal Q-values;
- Search improvement;
- policy/value model improvement;
- Battle controller promotion;
- complete-run improvement;
- T034 completion;
- Non-Combat improvement;
- deployment readiness; or
- T066 authorization.

## Out Of Scope

Do not perform or authorize in T098:

- native `sts_lightspeed` behavior changes;
- formal T096 4×8192 distribution rerun;
- 2→4→8→16→32 particle convergence;
- Oracle/Search aggregation across particles;
- Search modifications;
- model training;
- student target generation;
- controller promotion;
- complete-run evaluation;
- Non-Combat policy work;
- PRNG seed inference/reverse engineering;
- T034 closure;
- T066.

If the frozen native source is insufficient in a way that requires simulator
changes, terminate under the appropriate fidelity classification and return to
the governed native-change workflow.

## Successor Meaning

Only a successful `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY` terminal allows
Planner to publish a separate particle-count convergence task.

That successor may evaluate nested particle counts such as:

```text
2 -> 4 -> 8 -> 16 -> 32
```

on a bounded public-state cohort.

Poor convergence at tens of particles should be treated as an architecture /
economics warning rather than an automatic reason to scale to hundreds or
thousands.

## Execution Freedom And Material Changes

Maintainer/Implementer own ordinary implementation details including:

- exact bounded witness-generation method;
- helper/CLI/report layout;
- test decomposition;
- deterministic seeds;
- choice of supported non-mixed Runic Dome witness;
- whether Headbutt or Rebound supplies the primary known-top witness;
- artifact path;
- process topology.

A material change requires Planner amendment and renewed Maintainer exact-spec
approval if it changes:

- the exact native source commit;
- the required fidelity families;
- the supported-vs-intentional-unsupported distinction;
- public/legal-action parity requirements;
- the bounded sampling ceiling;
- terminal classifications;
- no-PRNG-cracking semantics;
- successor meaning;
- the prohibition on convergence/Search/training work.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, the Maintainer must independently review the exact task PR
head and post:

```text
SPEC APPROVED

task: T098
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not
require repeated Planner approval unless a material scientific/architecture
change above occurs.

Final landing requires Maintainer final implementation/operational acceptance and
Planner final scientific/architecture acceptance on the same exact final PR head.

Particle convergence, T034 closure, Search, training, controller promotion,
Non-Combat work, and T066 remain unauthorized.

## Candidate Result Record

Candidate lifecycle: `DONE`

Terminal classification: `PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY`

Implementation/evidence head:
`7f6adda6470e462f50b40ba7de269d6a3fccbabc`

The focused re-entry used the unchanged T097 native identity:

```text
repository: lsmfttb/sts_lightspeed
ref: refs/heads/stsrl/main
commit: d309170198e21e57041a84dcfdbc255cdda4052e
```

Four explicit portable assisted-run Battle anchors were replayed through the
repository's existing authoritative restore path. Each supported witness then
called the actual native `t096_public_information_projection` and
`sample_hidden_future_particles` APIs with exactly `N=32`:

- ordinary hidden draw / public exact intent: 32/32 public parity, 32/32
  ordered-public-legal-action parity, 31 hidden fingerprints;
- Headbutt exact known top: a native-legal bounded driver played Headbutt and
  selected Defend from discard, after which the projection classified a
  one-card `known_prefix`; 32/32 public parity, 32/32 legal parity, and 6
  hidden fingerprints showed that the unconstrained remainder still varied;
- Frozen Eye: the complete 14-card visible order was classified
  `full_public_exact` and remained identical for all 32 particles; one hidden
  fingerprint was observed and no hidden draw-order diversity is claimed;
- supported Runic Dome: current intent and current move/damage fields were
  absent, prior move and public-status surfaces remained present, and all
  32 particles preserved public/legal parity with 31 hidden fingerprints.

The native deterministic visibility audit separately exercised its Book of
Stabbing timing-mixed Runic Dome counter. It classified the surface
`unsupported_fidelity`, omitted the raw hidden roll, retained observed prior
move semantics, and rejected sampling. The complete audit also passed the
Headbutt/Rebound/Forethought, Frozen Eye, private-state firewall, semantic
counter, and supported private-misc cases. No raw RNG, sampler seed, hidden
fingerprint, or private native state entered a public projection or normal
controller/model input.

The compact report is retained at
`/mnt/d/DeadlyCatCoding/STSRL/artifacts/t098-public-information-fidelity-reentry-v1/t098-public-information-fidelity-reentry-v1.json`
(12,576 bytes, SHA-256
`7f399304980025a3b3c1009b18cd7c2af113e67231d46746dbc460e0914e72fd`).

The durable report-validation entrypoint is:

```text
cd /mnt/d/DeadlyCatCoding/STSRL-T098
PYTHONPATH=src python -m sts_combat_rl.commands.t098_public_information_fidelity \
  --input-report /mnt/d/DeadlyCatCoding/STSRL/artifacts/t098-public-information-fidelity-reentry-v1/t098-public-information-fidelity-reentry-v1.json
```

It consumes the input JSON report with schema
`t098-public-information-fidelity-reentry-v1`, verifies the frozen native
identity `lsmfttb/sts_lightspeed refs/heads/stsrl/main @
d309170198e21e57041a84dcfdbc255cdda4052e`, and requires the explicit
`intentional_unsupported_witness` evidence from
`StepSimulator.t096_visibility_audit` (`native-battle-visibility-audit-v1`).
The exact-source native build used by the report remains the T097 disposable
build (`STSRL_LIGHTSPEED_BUILD_JOBS=16`); this validator does not rebuild or
mutate native source.

The same module has a durable generation mode. With the exact pinned native
build directory on `PYTHONPATH`, the retained report is reproducible from the
explicit portable-pool records with:

```text
cd /mnt/d/DeadlyCatCoding/STSRL-T098
PYTHONPATH=<exact-d309170-build-dir>:src python3 -m sts_combat_rl.commands.t098_public_information_fidelity \
  --portable-pool /mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair/source/cohort-b-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c/cohort-b-merged.pool.jsonl \
  --output-report /mnt/d/DeadlyCatCoding/STSRL/artifacts/t098-public-information-fidelity-reentry-v1/t098-public-information-fidelity-reentry-v1.json \
  --implementation-head 7f6adda6470e462f50b40ba7de269d6a3fccbabc \
  --ordinary-record-index 0 --headbutt-record-index 73 \
  --frozen-eye-record-index 828 --runic-dome-record-index 475
```

Generation calls the existing `run_t098_fidelity_reentry` and
`write_t098_report` workflow, uses the fixed native identity
`d309170198e21e57041a84dcfdbc255cdda4052e`, and records the pool path and
indices in the report's `input_references`. `<exact-d309170-build-dir>` is the
`build-stsrl-source-py` directory produced by the pinned-source verifier; no
native source mutation is part of this command.
The successful validator output is retained as
`report-validation.log` (SHA-256
`70972562a0e8978e1cf68ca06d2e34ebc5ed08ce522027a1a82379c2251d9567`) beside
the report.

The exact-source native build log is `native-build.log` (SHA-256
`b5282e19e16acae8b926f9e7bb8bd909c3829c611b659b0f5b2d953b4b08318d`),
and the witness execution log is `runtime-evidence.log` (SHA-256
`e0c31a5d1cbee6fa6f5c9496382f1aa5ff3a66d7a027ccb9f5186589f17af5ec`)
in the same directory. The disposable exact-source build used 16 build workers
and passed the pinned-source verifier. The bounded witness replay used one
worker for 58.680 seconds;
single-worker execution was appropriate because this was one small,
deterministic, stateful witness sequence rather than source generation,
coverage, evaluation, comparison, or a formal cohort.

This result closes only the representative native visibility/fidelity blocker
that terminated T096. It does not establish particle-count sufficiency, an
exact posterior, arbitrary-mid-Battle universal support, Search or model
improvement, controller promotion, complete-run improvement, T034 completion,
Non-Combat improvement, deployment readiness, or T066 authorization. No
formal T096 4×8192 rerun, convergence ladder, Search, training, controller,
Non-Combat, or native-source change was performed.

Focused T098/T096/adapter/source-manifest verification passed 47 tests. Python
compileall, changed-file Ruff checks and format checks, `git diff --check`, and
both mock CLI fixtures passed. The task-doc/focused group passed 52 tests and
had one unrelated baseline failure for the pre-existing `Status:` field in
`docs/t092_canary_process_isolation_amendment.md`. The full WSL/Torch suite
completed with 1,379 passed, 2 skipped, and 33 failed. Those 33 are existing
baseline failures in historical exact-native-identity guards, the WSL
artifact-path fixture, T092 legacy assertions, and workflow documentation; no
T098-focused test failed.
