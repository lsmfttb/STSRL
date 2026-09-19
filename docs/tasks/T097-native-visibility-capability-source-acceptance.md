# T097: Native Visibility Capability Source Acceptance

Artifact Eligibility Required: false

## Objective

Accept the repaired `sts_lightspeed` visibility-aware Battle public-information capability into STSRL as one exact, reproducible native source dependency before any new scientific experiment uses it.

T097 is an **integration/provenance acceptance task**, not a scientific experiment.

The task exists because T096 terminated:

`NATIVE_PUBLIC_VISIBILITY_FIDELITY_INSUFFICIENT`

and the selected native repair has now been completed on the governed `sts_lightspeed` integration line.

The accepted native repair is:

- repository: `https://github.com/lsmfttb/sts_lightspeed.git`;
- branch/ref: `stsrl/main` / `refs/heads/stsrl/main`;
- previous STSRL manifest pin: `970fc15b67167bcf996fc20defd7b4a376583bc7`;
- native issue: `lsmfttb/sts_lightspeed#17`;
- reviewed PR: `lsmfttb/sts_lightspeed#18`;
- final independently reviewed PR head:
  `433abc1392076a80329c4625c57439d6bd062580`;
- merged native result:
  `d309170198e21e57041a84dcfdbc255cdda4052e`.

The sole task question is:

> can STSRL prove that this exact native result is on the accepted source lineage, pin it in the canonical source manifest, rebuild and verify it from a clean/disposable source checkout, and record the resulting information-regime capability without relying on local build residue or unrecorded source state?

A successful T097 does **not** prove the T096 scientific pilot now passes. It only establishes that the repaired native capability is a valid STSRL build input for a later focused fidelity re-entry.

## Publication Baseline

Publication base:

`main @ 9c9dc7e52408072bada7f2ce03d0394d86dce839`

The current STSRL source manifest still pins:

`970fc15b67167bcf996fc20defd7b4a376583bc7`

on:

`refs/heads/stsrl/main`.

T097 must advance that exact pin to:

`d309170198e21e57041a84dcfdbc255cdda4052e`

without changing the active integration branch.

## Dependencies

- T017: exact external source manifest and canonical source verifier.
- T020: single active `sts_lightspeed` integration-line governance.
- T096: sampler pilot whose terminal selected native visibility/fidelity repair.
- Native issue `lsmfttb/sts_lightspeed#17`.
- Native PR `lsmfttb/sts_lightspeed#18`, accepted on exact head
  `433abc1392076a80329c4625c57439d6bd062580` and merged as
  `d309170198e21e57041a84dcfdbc255cdda4052e`.

## Scope

### 1. Exact native source pin

Update `docs/sts_lightspeed_source_manifest.json` so:

- integration repository remains
  `https://github.com/lsmfttb/sts_lightspeed.git`;
- branch remains `stsrl/main`;
- ref remains `refs/heads/stsrl/main`;
- exact integration commit becomes
  `d309170198e21e57041a84dcfdbc255cdda4052e`.

No moving-ref-only dependency is acceptable. The exact commit remains the reproducibility authority.

### 2. Source lineage proof

The PR report must prove from the actual Git graph that:

- the previous accepted manifest pin
  `970fc15b67167bcf996fc20defd7b4a376583bc7`
  is an ancestor of
  `d309170198e21e57041a84dcfdbc255cdda4052e`;
- the final reviewed implementation head
  `433abc1392076a80329c4625c57439d6bd062580`
  is contained in the merged result lineage;
- the active `refs/heads/stsrl/main` resolves exactly to
  `d309170198e21e57041a84dcfdbc255cdda4052e`
  at acceptance time.

The exact Git commands and outputs used for those proofs must be reported.

A locally available commit with no accepted branch/ref lineage is not sufficient.

### 3. Canonical source verifier acceptance

The canonical source verifier remains the authority:

`scripts/verify_lightspeed_source.sh`

T097 must verify the new manifest identity from a clean/disposable native worktree produced by that verifier workflow.

The verifier must not succeed because of:

- a stale local `build-py`;
- an unrecorded native checkout;
- a temporary implementation branch;
- environment-only source overrides;
- files copied from a previous build.

If the existing verifier does not yet assert the repaired capability strongly enough, T097 may extend the verifier and focused source-manifest tests in STSRL. Such changes must remain generic source/capability verification work; they must not recreate native game mechanics in Python.

### 4. Capability inventory update

Update the manifest capability entry for the T096 native public-information / hidden-future sampler surface so it accurately describes the repaired native capability.

At minimum the accepted capability record must cover:

- versioned Battle public-information projection;
- current draw-knowledge state with exact known top/position constraints where supported;
- Frozen Eye full draw-order visibility;
- Runic Dome current-intent hiding;
- retention of previously observed move/history facts and visible statuses;
- typed unsupported draw-knowledge reasons;
- private-only monster hidden state omitted without falsely declaring the whole public state unsupported;
- semantic public monster counters;
- hidden-intent timing-mixed monster counters failing closed when separate epistemic provenance is unavailable;
- unsupported anchors rejected by the hidden-future sampler;
- accepted particles preserving the exact public projection and ordered public legal-action identities;
- deterministic native visibility audit surface.

The capability inventory should require the native APIs needed to verify these claims, including the existing T096 surfaces and the native visibility audit exposed by the accepted source.

Do not keep T096-era wording that says draw-knowledge and hidden-intent mechanics are generally still missing if that wording is no longer true. Known fail-closed unsupported cases should instead be described precisely.

## Information-Regime Contract

The capability accepted by T097 belongs to the normal-information/no-SL research line.

The permitted claim is:

> the exact pinned native source exposes a visibility-aware current-player-information state and a native public-consistent future-randomization proposal substrate with explicit fail-closed unsupported states.

T097 must not call the sampler:

- an IID posterior sampler;
- an exact Bayesian posterior over deterministic seed history;
- a proof of information-set-optimal search;
- a controller-improvement mechanism.

The no-PRNG-cracking boundary from T096 remains unchanged.

## Required Verification

At minimum, implementation must report and pass:

1. source-manifest parser/tests for the new exact integration identity;
2. exact Git lineage proof described above;
3. canonical disposable-worktree source verification:

   ```bash
   bash scripts/verify_lightspeed_source.sh /path/to/sts_lightspeed
   ```

4. native API smoke against the canonical verifier-built module;
5. the native deterministic visibility audit from the pinned source;
6. focused T096 particle smoke sufficient to prove the pinned module exposes the accepted sampler surface;
7. existing source-verifier / manifest regression tests;
8. ordinary repository quality gates required by `docs/tasks/README.md`.

The task may reuse the native PR's previously reported test results as provenance, but final T097 acceptance requires fresh verification against the exact source commit selected by the STSRL manifest.

If rebuilding the native source requires a bounded WSL build, report the exact build command and source identity. This task does not require formal 8192-particle evidence.

## Acceptance Criteria

T097 passes only if all of the following are true:

- STSRL manifest pins exactly
  `d309170198e21e57041a84dcfdbc255cdda4052e`;
- the active integration ref is still `refs/heads/stsrl/main`;
- the previous pin `970fc15b...` is proved to be an ancestor of the new result;
- the reviewed head `433abc139...` is proved to be included in the merged result lineage;
- the active integration ref resolves to the pinned commit;
- the canonical source verifier builds and verifies the pinned commit from a disposable source worktree;
- the verifier-built module exposes and passes the accepted visibility/public-information capability checks;
- native full-snapshot compatibility required by existing STSRL consumers remains intact;
- the manifest capability inventory no longer carries the obsolete T096 visibility-fidelity-gap wording;
- no Python mechanics reconstruction is introduced;
- no scientific T096 rerun, Search convergence experiment, training, controller promotion, Non-Combat update, T034 closure, or T066 work is performed.

The intended successful terminal is:

`NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED`

## Failure / Incomplete Conditions

Use `SOURCE_LINEAGE_INVALID` if the exact new source cannot be proved to descend from the accepted integration line or the active ref does not resolve to the pinned result.

Use `NATIVE_CAPABILITY_VERIFICATION_FAILED` if source lineage is valid but the canonical clean verifier/build/API/visibility checks fail.

Use `INCOMPLETE` if required source identity, verifier evidence, or capability provenance cannot be validly produced.

No failure terminal authorizes a scientific successor.

## Explicit Non-Claims

T097 does not establish:

- that T096's former terminal has scientifically reversed;
- `PUBLIC_HIDDEN_FUTURE_SAMPLER_PILOT_READY`;
- exact hidden-state posterior correctness;
- arbitrary-mid-Battle support;
- particle-count sufficiency;
- action-value or action-ranking convergence;
- Search improvement;
- model/student improvement;
- controller promotion;
- complete-run improvement;
- T034 completion;
- Non-Combat improvement; or
- T066 authorization.

## Out Of Scope

Do not perform or authorize in T097:

- the formal T096 4×8192 rerun;
- 2/4/8/16/32 particle convergence;
- multi-particle Oracle/Search aggregation;
- Search modifications;
- model training;
- controller promotion;
- complete-run evaluation;
- Non-Combat work;
- PRNG reverse engineering;
- new native simulator behavior changes.

If fresh native behavior changes are found necessary, T097 must stop and route them through the governed `sts_lightspeed` native-change workflow rather than modifying native source inside STSRL.

## Successor Meaning

A successful `NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED` terminal authorizes Planner to publish one **focused T096 fidelity re-entry** task.

That successor should test whether the exact native fidelity condition that caused T096 to terminate has actually been closed on representative draw-knowledge and intent-visibility states, while also checking that the previously passing ordinary hidden-draw sampler behavior has not regressed.

Particle-count convergence is downstream of that scientific re-entry. T097 does not authorize it directly.

## Execution Freedom And Material Changes

Maintainer/Implementer own ordinary implementation details including:

- exact verifier helper/test decomposition;
- manifest parser/test organization;
- shell/Git command formatting;
- local/WSL build orchestration;
- capability-description wording that preserves the contract;
- report layout.

A material change requires Planner amendment and renewed Maintainer exact-spec approval if it changes:

- the exact accepted native commit;
- the governed integration branch/ref;
- the required lineage relationship;
- the normal-information/no-PRNG-cracking claim boundary;
- the required capability semantics;
- the successful terminal meaning;
- the prohibition on running new scientific experiments inside T097;
- the successor ordering.

## Acceptance And Authorization Boundary

Publishing this task does not itself authorize implementation.

Before implementation, the Maintainer must independently review the exact task PR head and post:

```text
SPEC APPROVED

task: T097
approved_spec_commit: <exact task PR head>
implementation_authorized: true
```

After that approval, ordinary implementation changes on the same PR do not require repeated Planner approval unless a material contract change above occurs.

Final landing requires Maintainer final implementation/operational acceptance and Planner final architecture/provenance acceptance on the same exact final PR head.

T034 scientific closure, particle convergence, model training, controller promotion, Non-Combat work, and T066 remain unauthorized.

## Candidate Result Record

Candidate lifecycle: `DONE`

Terminal classification: `NATIVE_PUBLIC_INFORMATION_CAPABILITY_ACCEPTED`

The exact STSRL source manifest now pins:

```text
repository: https://github.com/lsmfttb/sts_lightspeed.git
branch: stsrl/main
ref: refs/heads/stsrl/main
commit: d309170198e21e57041a84dcfdbc255cdda4052e
```

Native lineage was verified against the actual Git graph. The previous pin
`970fc15b67167bcf996fc20defd7b4a376583bc7` is an ancestor of the pinned result,
the fetched `refs/pull/18/head` resolves to the independently reviewed head
`433abc1392076a80329c4625c57439d6bd062580`, that reviewed head is an ancestor
of the pinned result, and a fresh fetch of `refs/heads/stsrl/main` resolves
exactly to `d309170198e21e57041a84dcfdbc255cdda4052e`.

The canonical verifier was run with a fresh detached native worktree and fresh
`build-stsrl-source-py` directory created by the verifier:

```text
STSRL_LIGHTSPEED_BUILD_JOBS=16 bash scripts/verify_lightspeed_source.sh \
  /mnt/d/DeadlyCatCoding/sts_lightspeed
```

The successful run built the exact pinned native source with GCC 15.2.0 and
Python 3.14.4, imported the verifier-built extension from
`/tmp/stsrl-lightspeed-source.CmAbuY/build-stsrl-source-py`, and passed the
full STSRL native API assertions. The focused native sampler smoke passed with
`step=4`, `particles=8`, and `distinct_hidden=8`. The deterministic native
visibility audit passed all required fields, including known top/position
constraints, Frozen Eye full-order preservation, Runic Dome current-intent and
previous-history behavior, typed unsupported draw reasons, private-only hidden
state omission, semantic public counters, mixed-counter fail-closed behavior,
and direct unsupported-anchor rejection. Native Search-v2 tree-geometry smoke
also passed.

The fresh evidence logs are retained outside the review worktree under
`/mnt/d/DeadlyCatCoding/STSRL-T097-evidence/`:

- `native-lineage-proof.log`
- `verify_lightspeed_lineage.log`
- `verify_lightspeed_source-rerun.log`
- `verifier-rerun-exit.txt`

No simulator-scale or scientific T096 run was started. No native source was
modified. This result accepts the exact native capability as a reproducible
normal-information/no-SL build input; it does not reverse T096's scientific
pilot terminal, establish posterior correctness or particle-count sufficiency,
close T034, or authorize Search, training, controller, complete-run,
Non-Combat, or T066 work. A focused T096 fidelity re-entry remains a separate
successor task.

Repository checks on the final candidate tree passed for `git diff --check`,
shell syntax, Python compileall, changed-file Ruff checks, the 21 focused
manifest/T096 tests, and both mock CLI fixtures. The full repository suite
completed with 1,374 passed, 2 skipped, and 33 failed; the failures are outside
the T097 acceptance surface (historical exact-native-identity guards, the
pre-existing WSL artifact-path fixture, and pre-existing task/workflow
documentation assertions). No T097-focused test failed.
