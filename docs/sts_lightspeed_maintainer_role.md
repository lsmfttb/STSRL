# sts_lightspeed Maintainer Role

This maintainer-owned document defines how STSRL coordinates work in the
external [`lsmfttb/sts_lightspeed`](https://github.com/lsmfttb/sts_lightspeed)
fork. It is an operating contract for the fork role; it does not by itself
change the source pinned by STSRL. The STSRL source manifest and a reviewed
STSRL pull request remain the authority for which external simulator commit is
accepted by `main`.

## Purpose

STSRL uses `sts_lightspeed` as the current large-scale simulator substrate, but
the final game remains the mechanism authority. The fork exists to expose
native simulator surfaces needed by STSRL, not to become a second game
specification.

The `sts_lightspeed` maintainer role keeps native fork work reviewable,
reproducible, and separate from STSRL Python/controller work.

## Role Split

### STSRL Main Maintainer

The STSRL main maintainer owns:

- STSRL task boundaries and readiness;
- `docs/sts_lightspeed_source_manifest.json`;
- source-verifier requirements;
- Python adapters, public contracts, and artifact compatibility in STSRL;
- review of whether a native fork commit satisfies the STSRL task contract;
- merge decisions into STSRL `main`.

The STSRL main maintainer may perform small fork housekeeping such as verifying
refs, creating the documented active branch, or checking tags. They should not
normally implement native C++/pybind simulator features that they will later
accept into STSRL.

### sts_lightspeed Maintainer

The `sts_lightspeed` maintainer owns work in a separate fork workspace:

- native C++ and pybind implementation branches;
- build and test evidence from the fork;
- active integration branch hygiene;
- exact fork commands and commit identities reported back to STSRL;
- keeping historical task branches as provenance unless deletion is explicitly
  approved.

### STSRL Task Implementer

The STSRL task implementer owns STSRL-side work for a published task:

- Python adapter updates;
- manifest updates to an exact external commit;
- STSRL tests, docs, and source-verifier checks;
- PR evidence tying the STSRL change to the accepted fork commit.

One STSRL pull request may depend on one external fork commit, but it must still
be reviewable as a normal STSRL task branch.

## Workspace Boundary

The fork checkout stays outside this repository. Typical local paths are:

```text
STSRL workspace:          D:\DeadlycatCoding\STSRL
WSL simulator checkout:   ~/stsrl-spikes/sts_lightspeed
WSL system build:         ~/stsrl-spikes/sts_lightspeed/build-py
```

Do not vendor simulator source, build products, game files, save files, jars,
or large binaries into STSRL. STSRL stores the manifest, verifier, adapters,
tests, and documentation.

## Branch Policy

The fork should have exactly one active STSRL integration branch:

```text
stsrl/main
```

That branch is a human-friendly maintenance line. Reproducibility still comes
from the exact commit recorded in `docs/sts_lightspeed_source_manifest.json`.

Recommended fork refs:

```text
stsrl/main                    # only active integration line
work/T0XX-short-name          # temporary native implementation branch
stsrl-source/T0XX             # optional immutable tag for accepted source point
```

Historical task-shaped branches such as `stsrl/t006-*`, `stsrl/t008-*`,
`stsrl/t017-*`, and `stsrl/t018-*` may remain as provenance. They are not the
normal build input once `stsrl/main` is established by the accepted T020
workflow.

Rules:

- Do not force-push over a commit already referenced by an STSRL manifest or PR
  report.
- Do not delete historical task branches unless the STSRL main maintainer
  explicitly approves that cleanup.
- Do not rely on local unpushed branch state for STSRL gates.
- Do not make STSRL depend on a moving branch alone; always pin an exact commit
  in the manifest.
- Do not reopen the retired STSRL patch-stack workflow unless a new STSRL task
  explicitly does so.

## Native Task Lifecycle

Use this sequence for native-heavy work:

1. The STSRL main maintainer publishes a `READY` STSRL task that names the
   required native capability, information regime, public API, and verifier
   assertions.
2. The `sts_lightspeed` maintainer creates a temporary fork branch from the
   current active integration commit.
3. Native implementation stays minimal: expose required API and telemetry, but
   do not change game mechanics for training convenience.
4. The fork change is reviewed or otherwise made auditable with a compare link,
   commit list, and build evidence.
5. The active integration branch advances to the accepted fork commit.
6. A STSRL PR updates `docs/sts_lightspeed_source_manifest.json` to the exact
   new commit and updates adapters, tests, docs, and source-verifier assertions.
7. The STSRL verifier builds from a disposable checkout of the manifest commit.
8. Only after the STSRL PR merges is the new native surface an implemented STSRL
   capability.

If a native task also needs STSRL Python adapter changes, keep the fork commit
and the STSRL branch separately reviewable. The PR report must make the
cross-repository dependency explicit.

## Information And Mechanics Boundary

Native fork changes must preserve STSRL information-regime rules:

- Normal-information paths must not receive hidden RNG, unrevealed future
  encounters, hidden draw order, hidden Act-3 second Boss, or other hidden
  simulator state.
- Oracle-like native search surfaces must declare
  `full_simulator_state_oracle_like` and must not be reported as
  normal-information performance.
- Public projection APIs must report missing visible context explicitly instead
  of filling it with guessed or hidden data.
- Simulator state mutation, legal-action enumeration, battle-start restore,
  encounter selection, and hidden future sampling must come from the simulator,
  not STSRL Python reimplementations.

Native fork work must not deliberately alter Slay the Spire mechanics unless
the task is an explicitly documented parity/build fix. If a discovered upstream
behavior appears wrong, report it as a compatibility risk and keep the STSRL
claim conservative.

## Required Fork Evidence

A STSRL PR that consumes a new fork commit must report:

- external repository URL;
- previous and new active integration refs;
- previous and new exact commits;
- fork branch commands or merge commands used;
- whether tags were created;
- whether any historical branches were deleted;
- native build command and result;
- source-verifier command and result;
- new or changed native Python API names;
- information-regime classification for any search or projection surface;
- known parity, missingness, or build risks.

For branch-maintenance-only work, the PR must still report `git ls-remote`
evidence proving the documented branch resolves to the manifest commit.

## Review Checklist

Before accepting a STSRL PR that updates the source manifest, the STSRL main
maintainer checks:

- the manifest repository URL, branch/ref, and commit are exact and fetchable;
- the active branch policy is preserved;
- the source verifier builds from a clean/disposable checkout;
- required native capability assertions pass;
- no unrecorded local fork state is required;
- old task branches are not presented as normal build inputs;
- no game files, build artifacts, or simulator source were vendored into STSRL;
- no normal-information path receives hidden simulator state;
- WSL commands and source identity reports name the new ref/commit.

## Emergency Maintenance

The STSRL main maintainer may perform small external-fork housekeeping when it
does not change native code, such as:

- creating or repairing the active integration branch at an already accepted
  exact commit;
- verifying remote refs;
- creating immutable provenance tags;
- documenting branch disposition.

Native code changes should go through the `sts_lightspeed` maintainer role even
when they are small. Keeping implementation and acceptance separate is more
important than saving a short branch.

## Updating This Document

Update this document when:

- the active branch policy changes;
- the fork gains a new permanent maintainer workflow;
- STSRL changes how source manifests or verifier checks work;
- branch deletion, tag policy, or upstream synchronization rules become more
  specific.

Do not use this document to mark a native capability implemented. Implemented
capabilities belong in `current_status.md` only after the relevant STSRL PR
merges into `main`.
