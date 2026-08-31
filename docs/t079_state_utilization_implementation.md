# T079 state-utilization bounds implementation

This document describes the recovery implementation for PR #84.  It is an
observation-only adapter around the native
`StepSimulator.battle_search_v2_with_state_utilization` API.  It does not alter
Search v2 traversal, allocation, callbacks, simulator execution, or root
selection.

## Identity evidence

Native state-utilization v1 reports canonical identity completeness at call
scope.  A complete call is normalized into `exact_comparable` rows and its
canonical digest/equality evidence is validated.  If native reports an
incomplete identity, every row in that call is conservatively normalized to
`opaque`; its native digest and first-seen fields are discarded.  Opaque rows
retain only ordinal, depth, path traversal evidence, and the native reason.

This is deliberate: the active native model stores queued actions as opaque
`std::function<void(BattleContext&)>` values.  T079 recovery does not
semanticize those continuations and never uses function addresses,
`target_type`, queue position, or path identity as state equality.

## Bounds

For `N` rows, `C` comparable rows, `O` opaque rows, `U` unique comparable
states, and `D=C-U`, the reducer emits:

```text
exact_duplicate_fraction_lower = D/N
exact_duplicate_fraction_upper = (D+O)/N
unique_state_yield_lower = U/N
unique_state_yield_upper = (U+O)/N
```

Prefix checks compare ordered path/action fingerprints only.  In a verified
prefix interval, exact-comparable first appearances contribute to the lower
marginal yield; opaque rows contribute only to its upper bound.  No prefix or
state equality claim is produced for malformed evidence.

## Reproducible integration boundary

Scientific execution must use the active `sts_lightspeed` integration
`refs/heads/stsrl/main`, not a temporary work branch, and must pass the real
telemetry-off/on parity and T078 restore-fidelity preflight first.  The frozen
stages remain S100/S400/S1600 over the exact retained 16-record cohort with
16 one-record shards and 16 effective workers.  This implementation slice does
not run those stages; Maintainer review is required before science.
