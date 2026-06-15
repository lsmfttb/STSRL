# Experiment Log

This file preserves concise, dated evidence that still informs current work.
It is not an architectural contract and does not define current defaults.
Artifact paths and command options may age; verify them before reuse.

## 2026-06-15: Public Run Context

- A rebuilt WSL A20 collection produced a current pool with 18
  restore-verified battle starts.
- Every record carried the visible Act Boss, visible map, current node, and
  next nodes.
- First-battle encounter history was empty; later history length matched the
  battle index.
- A forbidden-field audit found no hidden Act-3 second Boss, future encounter
  lists, or RNG state.
- A two-battle search-training smoke preserved the sanitized context in all 18
  decision records.

Conclusion: the current encounter/map context path is wired correctly, but it
is not yet the complete player-visible run history and the flat scorer does not
use it.

## 2026-06-14: Natural A20 Coverage

The calibrated `stratified-random-v2` non-combat driver and a
20-simulation no-potion Oracle-like battle controller produced:

```text
1,000 terminal runs
4,696 restore-verified battle starts
3,888 normal + 755 elite + 18 event battle + 35 Boss
4,695 Act 1 + 1 Act 2 battle start
```

The same run audit observed 255 potion discards, 48 non-combat potion uses, 28
treasure leaves, and 127 keys.

Conclusion: stochastic branch coverage works, but the battle controller and
incoming-state distribution still produce almost no later-act A20 data.

## 2026-06-14: Boss And First Act-2 Diagnosis

- Of 35 Act 1 Boss starts, no-potion Oracle-like search won `1/35` at 20
  simulations, `4/35` at 100, and `7/35` at 500.
- Potion-enabled search won `2/35` at 20 and `8/35` at 100.
- The only reached Act 2 checkpoint entered `CHOSEN` at `69/82` HP. It lost at
  20 no-potion simulations, won at 100 no-potion simulations with 61 HP, and
  won at 20 potion-enabled simulations with 73 HP.

Conclusion: the lone Act 2 start was not intrinsically losing. Search budget
and potion handling materially affect natural later-act reachability.

## 2026-06-14: Resource Outcome Contract

- Terminal resource outcomes preserved potion identity, deck/curse changes,
  relic additions/removals and persistent data, keys, HP/max-HP, and gold
  changes across a real WSL collection gate.
- The PyTorch resource head completed train/save/reload/evaluate with
  per-component error reporting.

Conclusion: the contract is usable for model plumbing, but no learned
continuation value has been demonstrated.

## 2026-06-14: DAgger Iteration Rejected

- Initial teacher set: 30 battles and 295 decisions.
- Held-out set: 15 battles and 137 decisions.
- DAgger behavior set: 30 battles and 376 decisions; behavior/teacher agreement
  was `172/376`.
- Natural-run average final floor improved from `6.64` to `6.97`, but all runs
  still died.
- Held-out teacher agreement and fixed-cohort results regressed.
- Both compared models lost all nine fixed Act 1 elite battles.

Conclusion: reject the iteration. Small-data fit and raw floor movement are not
sufficient promotion evidence.

## Earlier Search Calibration

On A20 seeds 1-10:

```text
preferred-kind battle baseline average floor: 7.7
20-simulation highest-mean Oracle-like search: 8.1
100-simulation highest-mean Oracle-like search: 8.0
best compressed soft-root-visit model: 7.7
```

Conclusion: direct search cleared the simple fixed baseline, while model
compression did not. These small results are calibration only.

## Simulator And Checkpoint Gates

- The external `sts_lightspeed` Python module built and imported in WSL.
- Complete first-battle checkpoint replay passed at A0 and A20.
- Portable battle-start manifests restored in fresh WSL processes.
- Duplicate public action ids required replay traces to preserve action
  occurrence as well as action id.

Historical simulator comparisons and early trainer experiments are retained in
[`history/`](history/README.md).
