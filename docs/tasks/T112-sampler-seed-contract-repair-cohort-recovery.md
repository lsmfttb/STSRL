# T112: Sampler-Seed Contract Repair and Bounded N=2 Cohort Recovery

Artifact Eligibility Required: true

## Objective

Repair the STSRL-side sampler-seed contract bug exposed by T111, then immediately re-run only the bounded configured-Search-domain N=2 support gate needed to determine whether the original T101 convergence cohort can be recovered.

T112 deliberately combines diagnosis closure, the minimal validator repair, regression proof, and bounded cohort recovery in one task. It must not be split into a new taxonomy-only diagnostic followed by a separate repair/replay task unless the approved repair boundary proves impossible without a native `sts_lightspeed` change.

The falsifiable question is:

> after correcting the erroneous requirement that each native particle's derived `sampler_seed` equal the bridge-level `sampler_seed_input`, can the frozen T111 configured-Search-domain selector obtain the first 8 admissible states in each A/B/C stratum under exact N=2, Search-v2@400, replicate 0, and `include_potions=false`?

A successful T112 establishes only a recovered 24-state N=2 support cohort for a later particle-count convergence task. It does not itself authorize N>2 convergence, training, promotion, or full-controller evaluation.

## Publication Baseline

Publication base:

`main @ 672db06b937cb4e0b80423a92669b582917fae57`

Accepted native integration remains:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 6496fc1c7e629a374b72bd94f7fd29afe29c7f62`

Accepted predecessor terminals:

- T110: `NATIVE_CONFIGURATION_AWARE_ROOT_MAPPING_ACCEPTED`;
- T111: `CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT`, with exact bounded distribution over 413 attempted source identities: `385` `v2_bridge_schema_or_classification_failure`, `8` searched-value unavailable/nonfinite/unvisited, and `20` accepted structured bridge/public-fidelity failures; admitted A/B/C = `0/0/0`.

## Static Root Cause Already Established

T112 starts from the following source-level facts and must preserve them as the repair rationale rather than reopening a broad diagnosis:

1. T101/T111 derive one deterministic bridge input seed `S` from the exact selection identity and replicate index.
2. Native `sample_hidden_future_particles_search` receives `S` as `sampler_seed_input`.
3. Native does **not** copy `S` into each particle row. `buildHiddenFutureParticle` computes a per-particle derived seed with native `hiddenParticleSeed(S, particle_index)` and returns that derived value as `particles[i].sampler_seed`.
4. Native direct-sampler parity audits compare each bridge particle's derived seed with the corresponding direct sampler particle's derived seed; they do not require the derived seed to equal `S`.
5. T111 nevertheless rejects any returned particle whose `particle["sampler_seed"] != expected_sampler_seed`, where `expected_sampler_seed` is `S`.
6. T111 unit fixtures currently mask this mismatch by synthesizing reports in which both particles' `sampler_seed` fields are manually set equal to the bridge input seed.
7. The same historical equality assumption is present in T101 validation and must not remain as an authoritative seed invariant for future reuse.
8. The exact T111 aggregate count is consistent with this bug being the dominant post-bridge rejection: `413 - 20 - 8 = 385`. This arithmetic is supporting evidence, not a claim that retained coarse T111 evidence individually proves all 385 rows failed on that exact predicate.

These facts are sufficient to authorize a narrow STSRL validator repair. T112 must not add native telemetry or perform a 385-case diagnostic census to reconfirm them.

## Correct Seed Contract

The repaired contract is:

- `derive_t101_sampler_seed(selection_identity, replicate_index)` yields the bridge-level sampler input seed `S`;
- `report["sampler_seed_input"]` MUST equal `S`;
- `particle["sampler_seed"]` is a native-owned per-particle derived seed associated with that particle index;
- STSRL MUST NOT require `particle["sampler_seed"] == S`;
- STSRL MUST NOT reimplement, duplicate, or independently predict native `hiddenParticleSeed` in Python;
- per-particle seed fields remain subject to the accepted strict bridge schema/type/index validation and exact native-source provenance;
- native direct-sampler parity remains the authoritative proof that bridge particle sampling uses the accepted native distribution;
- native derivation of per-particle streams from one bridge input is not a retry or reseed and must not be mislabeled as one;
- changing `sampler_seed_input`, replicate index, source identity, particle range, or executing a second bridge attempt remains prohibited.

No other T110/T111 bridge, mapping, searched-value, classification, partition, projection, or provenance rule is relaxed by this repair.

## Implementation Scope

T112 may modify STSRL code/tests/docs needed to remove the false seed-equality invariant and centralize the correct bridge-input-vs-derived-particle distinction.

Required implementation behavior:

1. T111 configured-search validation must continue to require exact `sampler_seed_input == expected S`.
2. It must no longer require every particle's native-derived `sampler_seed` to equal `S`.
3. Any shared or historical T101 helper that would otherwise propagate the false equality invariant into future convergence work must be corrected or explicitly retired from the active path. Historical artifacts are not rewritten and historical experiment outputs are not retrospectively reclassified by code mutation alone.
4. Do not weaken T099/T110 schema validation beyond the seed semantic correction.
5. Do not accept missing/non-integer particle seeds, unordered/mismatched particle indices, unknown bridge schema, or native/source drift.
6. Do not add a Python implementation of native seed mixing merely to make tests deterministic.

If implementation unexpectedly requires changing `sts_lightspeed`, STOP and report a blocker. T112 does not authorize a native repository change.

## Required Regression Proof

Before any cohort execution, tests must prove all of the following:

### A. Realistic derived-seed report is accepted

A valid N=2 v2 report with:

- `sampler_seed_input = S`;
- particle 0/1 carrying valid native-style derived seed values that are not forced equal to `S`;
- otherwise valid strict T110 v2 schema/classification/search values;

must pass the T112/T111 configured-domain validator.

The test fixture must no longer synthesize `particle.samper_seed == sampler_seed_input` as the normal case. (`sampler_seed` spelling in production schema remains unchanged; this sentence does not rename the field.)

### B. Bridge input mutation still fails closed

If `report["sampler_seed_input"] != expected S`, validation must fail closed.

### C. Particle metadata remains strict

Missing, malformed, boolean, or otherwise schema-invalid per-particle seed metadata must still fail through the accepted strict bridge validator. T112 must not turn particle seed into ignored arbitrary payload.

### D. Exact native witness

Using the accepted native pin, run the smallest deterministic supported N=2 bridge witness needed to show:

- the actual report's `sampler_seed_input` equals the requested bridge seed;
- returned particle seeds are native-derived particle metadata rather than an echo requirement;
- the corrected STSRL validator accepts that actual native report;
- no second attempt, retry, fallback, or reseed occurs.

One deterministic witness is enough. Do not run the 385 retained failures as a validation step.

### E. Existing boundaries remain fail-closed

Regression tests must retain at least:

- T110 strict configuration-excluded potion null semantics;
- Search-edge coverage;
- searched/excluded partition stability;
- searched finite/visited value requirements;
- public projection and ordered public-action parity;
- v1/v2 schema separation;
- unknown classification/schema rejection;
- no numeric imputation for excluded actions.

## Artifact Eligibility and Reuse

Before candidate execution, qualify the exact T111/T101 source population, restore bindings, current native source manifest, and any retained T111 report material proposed for reuse.

If exact raw/sanitized T111 bridge reports are retained with complete provenance and are sufficient to revalidate under the corrected seed contract without reconstructing private state, T112 MAY reuse them to avoid duplicate Search work.

If such reports are absent, incomplete, or scientifically ineligible, do not fabricate or regenerate a replacement artifact set. Instead use the accepted exact source population and perform the bounded selector below.

Retained T111 coarse exclusion labels alone are not sufficient to admit a state.

## Frozen Bounded Cohort Recovery

The scientific gate remains the T111 configured Search-domain contract except for the corrected seed invariant above.

Freeze:

- exact original 413 T101 source identities: A/B/C `93/192/128`;
- exact original per-stratum deterministic hash order;
- native pin `6496fc1c7e629a374b72bd94f7fd29afe29c7f62`;
- particle start `0`;
- `N=2`;
- replicate `0` and existing T101 bridge-input seed derivation;
- unguided Search-v2;
- `400` simulations per particle;
- `include_potions=false`;
- policy prior off;
- learned leaf value off;
- progressive bias off;
- exactly one bridge call per newly executed candidate;
- no retry, fallback, reseed, candidate substitution, hidden-state preselection, value-based preselection, or historical-failure preselection.

For each A/B/C stratum independently:

1. iterate in the exact original deterministic order;
2. admit only through the corrected strict configured-domain contract;
3. stop that stratum immediately when the first 8 admissible identities are obtained;
4. if the stratum exhausts before 8, retain the structured remaining exclusion distribution and stop with insufficient support.

Do not continue after 8 merely to estimate prevalence. A second full-413 census is not authorized automatically.

Previously observed 20 public-fidelity/structured failures, 8 searched-value failures, and any projection-parity failures exposed only after removal of the seed blocker remain ordinary support exclusions unless they actually prevent a stratum from reaching 8. Do not open separate diagnoses for them inside T112 unless the stratum would otherwise be exhausted; even then, T112 records the blocking distribution and stops rather than expanding into unbounded repair work.

## Terminal Classification

T112 has only these scientific terminals:

### `SAMPLER_SEED_CONTRACT_REPAIR_INVALID`

The proposed validator change cannot preserve the exact native/source/bridge contract, the deterministic native witness fails, artifact eligibility fails materially, or the repair requires an unauthorized native change. No cohort execution proceeds.

### `CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED`

All A/B/C strata reach the first 8 admissible states under the corrected contract. Retain exactly those first 8 identities per stratum and stop. This terminal permits Planner to define a later N=2→4→8→16→32 convergence successor; it does not execute it.

### `CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT`

At least one stratum exhausts before 8 after the seed repair. Retain only the bounded attempted rows and structured exclusion distribution needed for the Planner to choose the next blocking direction. No automatic larger replay or new native task follows.

## Required Outputs

Retain stable-schema artifacts for at least:

- validator-repair provenance and exact changed invariants;
- artifact qualification/reuse decision;
- deterministic native N=2 witness;
- ordered bounded candidate-attempt rows actually needed after repair;
- recovered cohort identities if successful;
- compact final report;
- retention manifest with SHA-256 identities;
- execution/resource evidence if new native Search calls are required.

Candidate evidence must distinguish bridge input seed from native per-particle derived seed semantically, but must not expose private RNG state or add hidden-state payloads.

## Acceptance Criteria

T112 passes only if:

1. the false particle-seed-equals-bridge-seed invariant is removed from every active path that would govern T112/future convergence reuse;
2. exact bridge input seed verification remains fail-closed;
3. per-particle native seed metadata remains schema-validated without Python reimplementation of native mixing;
4. a real exact-native N=2 witness passes the corrected validator;
5. all T099/T110/T111 non-seed structural/scientific boundaries remain unchanged and tested;
6. no native source change is made;
7. no 385-case diagnostic census is run merely to reconfirm the bug;
8. cohort recovery uses the exact source order and stops each stratum at first 8 or exhaustion;
9. every newly executed candidate has exactly one N=2 bridge call with no retry/reseed;
10. no N>2 convergence, training, promotion, complete-run evaluation, or unrelated failure-lane repair occurs;
11. lifecycle/current-status records accurately state the terminal and the exact recovered/remaining support result before final dual acceptance.

## Planner Decision Boundary After T112

If `CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED`, the next Planner decision may define one convergence task using the recovered 24-state cohort; do not insert another support-verification task solely to prove the same recovery again.

If `CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT`, choose the next direction from the actual residual blocking distribution. Do not automatically create one task per failure class.
