# T092 Canary Process-Isolation Contract Amendment

This amendment is the authoritative T092 execution-contract amendment on PR
#106. It supersedes only the process/native-loading semantics of the
`## Semantic-Parity Canary` and related execution-authorization text in
`docs/tasks/T092-internal-search-state-teacher-data-surface.md`. All other T092
scientific predicates, thresholds, candidate-state semantics, source cohort,
action-space accounting, information boundary, terminal classifications, and
successor logic remain unchanged.

## Reason for amendment

The previously prepared canary runner attempted to construct the OFF and ON native adapters inside one CPython process. Independent Maintainer runtime checking showed that, after loading the publication `slaythespire` extension, deleting it from `sys.modules`, replacing `sys.path`, and invalidating import caches, CPython still resolved the publication extension. A same-process factory can therefore silently execute both arms against the same publication native build while reporting different intended provenance.

That behavior is scientifically unacceptable because the T092 paired canary is intended to test:

- OFF: the unchanged accepted publication Search-v2@400 controller;
- ON: the task-scoped telemetry-native build with the same frozen controller semantics plus read-only telemetry.

The provenance distinction must be enforced by the execution boundary, not inferred from requested module paths or metadata.

## Frozen arm identities

The paired canary preserves the existing arm semantics:

- **OFF arm:** publication native `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 20a6c2b3a9cea817c988178b814f083ff889853f`, using the unchanged publication `battle_search_v2` API and telemetry disabled/nonexistent;
- **ON arm:** the exact task-scoped telemetry-native commit descended from the publication native base and pinned on PR #106 before canary authorization, using the reviewed telemetry API with telemetry enabled.

The current reviewed task-scoped native identity at publication of this amendment is `a439c70b568eab78dea42fe857dab56fa27cda3f`, descended from the previously reviewed telemetry head `07e1770cf0710d8c26719c153383d09e3bfd7686` and ultimately from publication base `20a6c2b3a9cea817c988178b814f083ff889853f`. If that native identity changes before the real canary, the replacement identity/diff must receive the normal Maintainer implementation review before canary authorization.

T092 does **not** relax the canary to permit both arms to use the task-scoped telemetry-native binary. Keeping OFF on the accepted publication native provides the stronger and already-published semantic-parity comparator.

## Required arm-isolated execution boundary

For every one of the exact 12 selected Battle starts:

1. OFF and ON must execute in **separate fresh OS processes** with separate Python interpreters. Process/container isolation stronger than a fresh process is allowed, but weaker in-process module swapping is not.
2. Each arm process may load exactly one `slaythespire` native extension build for its lifetime.
3. No Python process used for a scientific-quality canary arm may import, unload, reload, or path-swap between the publication and task-scoped native builds.
4. Each arm must independently restore the same exact accepted checkpoint/RNG state with no reseed and must consume the same occurrence-safe source identity and accepted restore inputs.
5. OFF and ON must not share mutable simulator objects, native module objects, RNG objects, or process-local caches. Their only pairing channel is the retained immutable arm-record protocol described below.
6. Parallel scheduling is permitted because pairing is by exact source/restore identity, not by wall-clock order. Worker topology must remain auditable and must not allow one process to service both arms with different requested native paths.
7. The process launcher must fail closed before constructing a simulator if the resolved native identity/binary does not match the arm-specific expected identity.

A single-process OFF/ON factory is explicitly forbidden for scientific-quality T092 canary evidence.

## Retained arm-record protocol

Each arm process must write one immutable, independently validatable arm record before pair comparison. At minimum the record must bind:

- T092 canary schema/version;
- arm identity (`OFF` or `ON`);
- exact occurrence-safe source identity, source group, inherited split, and deterministic canary selection identity;
- exact accepted restore/checkpoint/RNG identity or retained hash/reference required by the existing restore contract;
- exact STSRL execution head;
- exact native repository/ref/commit identity and an independently retained native binary/build hash;
- exact native API/schema/information-regime identity;
- frozen Search-v2@400 configuration, including simulations requested, no-potion regime, highest-mean root selection, no prior, no learned leaf value, `playoutRandom`, and `evaluateEndState`;
- restore public/legal parity evidence required by the existing canary contract;
- complete ordered root decision records with strict action identity, visit, finite-mean, selected-action, root-selection, and Search-work fields;
- authoritative terminal Battle evidence and decision count;
- arm-specific controller/Search cost fields;
- for ON only, the fail-closed validated depth>=1 internal occurrence payload or retained occurrence artifact reference/hash plus telemetry-only cost/bytes fields;
- artifact SHA-256/size and any shard/worker identity needed for retention provenance.

Missing, malformed, conflicting, default-inferred, filename-inferred, or arm-inappropriate provenance fails closed to `INCOMPLETE` before semantic-parity interpretation.

## Offline pair validation

Pair validation occurs only after both independently produced arm records pass their own arm-level validation.

For each selected start, the pair validator must require exact equality of the source/restore pairing identity and then enforce the already-published T092 semantic-parity predicates for:

- ordered root legal/searchable action identities;
- child/root visits and finite means;
- selected action identity and root-selection rule;
- Search work counters excluding explicitly separate telemetry-extraction cost;
- root decision sequence/count;
- authoritative terminal Battle outcome and retained T087-compatible terminal diagnostics.

The validator must additionally require:

- OFF native identity/build evidence matches the publication native exactly;
- ON native identity/build evidence matches the exact reviewed task-scoped telemetry-native identity;
- the two arm records are distinct retained artifacts produced by distinct process executions;
- OFF contains no ON-only internal telemetry payload;
- ON internal rows satisfy the existing depth>=1, schema, frozen-teacher, public-firewall, visit/mean, source/split/parent and duplicate constraints.

An arm provenance/identity failure is `INCOMPLETE`, not a Search semantic mismatch. A parity mismatch after both arms are provenance-valid remains `INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID` under the existing T092 terminal logic.

## Canary authorization boundary

This amendment does not itself authorize execution.

After Maintainer exact-head approval of the PR head containing this amendment, implementation may perform only the bounded canary-runner repair needed to:

- replace the same-process OFF/ON native factory with arm-isolated subprocess execution;
- retain and validate the arm records above;
- pair them offline using the existing canary selection and parity predicates.

The repaired exact STSRL head and unchanged or newly pinned task-native identity must then receive a fresh Maintainer implementation/readiness review. The real 12-start canary still requires a separate explicit Maintainer `CANARY_AUTHORIZED` gate. The exact 413-start formal collection remains unauthorized until canary evidence is reviewed.

## Formal-collection boundary

This amendment changes only the paired canary execution boundary. It does not change the formal 413-start controller/data-surface semantics.

Formal collection, if later authorized, continues to use the exact reviewed task-scoped telemetry-native build with telemetry enabled on the exact T087/T090 413-start cohort, subject to the existing root-reproduction, information-boundary, density/diversity/cost, artifact-eligibility and terminal-classification predicates.

## Scientific interpretation

The process split is execution isolation, not an additional experimental treatment. The intended comparison remains exactly:

```text
same accepted Battle start + same checkpoint/RNG state + same frozen Search-v2@400 semantics

OFF: accepted publication native, no internal telemetry
ON:  reviewed task-native, read-only internal telemetry enabled
```

The amendment exists solely to make those two arm identities physically enforceable and auditable in CPython.
