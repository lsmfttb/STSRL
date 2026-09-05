# Native Simulator Lineage Checklist

Use this checklist whenever an STSRL task changes the accepted `sts_lightspeed`
source identity.

The authoritative policy is
[`sts_lightspeed_maintainer_role.md`](sts_lightspeed_maintainer_role.md). This
checklist is intentionally short so it can be used during long-running task
execution without re-reading the full policy.

## Before Native Work

Record from the current STSRL manifest:

```text
native_base_ref: refs/heads/stsrl/main
native_base_commit: <exact SHA>
```

Then fetch the fork and require remote `refs/heads/stsrl/main` to resolve to that
same exact commit. If it does not, stop and reconcile before implementation.

Create native work only from that accepted base:

```text
work/T0XX-short-name
```

A temporary `work/*` branch is never a formal STSRL dependency.

## Risk Classification

Mark the native change as `low` or `high`.

`high` includes any change to RNG, state/screen transitions, checkpoint/restore,
legal actions or action execution, terminal/outcome semantics,
`evaluateEndState`, search selection/expansion/rollout/backup/allocation/root
selection, hidden-state exposure, or game-mechanics/parity behavior.

High-risk changes require an independent native semantic review of the exact
native head before acceptance. The reviewer must not be the author of that
native change. A dedicated simulator agent is optional, not mandatory.

## Before Updating The STSRL Manifest

The native change must first be integrated into remote `stsrl/main`.

Record:

```text
native_result_ref: refs/heads/stsrl/main
native_result_commit: <exact SHA>
```

Run:

```bash
bash scripts/verify_lightspeed_lineage.sh \
  /home/lsmft/stsrl-spikes/sts_lightspeed \
  <native_base_commit>
```

The gate must prove:

```text
native_base --ancestor--> native_result
native_result == remote refs/heads/stsrl/main
native_result == manifest integration commit
```

Then run the canonical clean source verifier:

```bash
bash scripts/verify_lightspeed_source.sh \
  /home/lsmft/stsrl-spikes/sts_lightspeed
```

Do not pin a temporary branch to make a failed lineage check pass.

## STSRL PR Evidence

Record at least:

```text
native_change_required: true
native_risk: low | high
native_base_commit: <SHA>
native_work_branch: work/T0XX-...
native_result_commit: <SHA>
lineage_check: PASS
independent_native_review: not-required | <evidence>
```

Also report the fork PR/compare link, native build/tests, information-regime
impact, source-verifier result, and the earliest STSRL stage that must be rerun.

## After STSRL Acceptance

Delete merged temporary `work/T0XX-*` branches unless there is an explicit
retention reason. Preserve provenance through the PR, commit SHA, and optional
immutable tag instead of long-lived working branches.
