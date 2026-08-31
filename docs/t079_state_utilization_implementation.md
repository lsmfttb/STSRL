# T079 implementation and execution contract

The T079 implementation is intentionally observation-only. `BattleSearchV2Controller`
selects the same `prior_value` search path, root rule, callbacks, and search budget
as T070; the enabled flag only selects the native companion API and validates its
telemetry after the search returns. Exact identity is native future-dynamics state,
including hidden card/order state, the current `CardQueueItem`, and all relevant
RNG streams. The native digest
is an aggregation key only; canonical payload equality is checked within every
digest bucket and the adapter rejects incomplete identity or any collision.

`src/sts_combat_rl/commands/t079_state_utilization.py` executes each budget as 16
one-record shards in 16 forked WSL processes. Every stage record contains its
configured and effective worker counts, shard range, PID, monotonic start/end
interval, and observed peak overlap. The stage validator derives peak concurrency
from those intervals and rejects configured-only claims, duplicate/missing records,
or malformed occurrence/path evidence.

The native identity audit covers every non-static field of `BattleContext`,
`Player`, `MonsterGroup`/`Monster`, `CardManager`, `CardSelectInfo`,
`CardQueue`/`CardQueueItem`, `CardInstance`, and all six `Random` streams.
`curCardQueueItem` is included independently of `cardQueue.size` because card
effects read it during execution. `ActionQueue` indices, size, and clear bits
are included; a non-empty action queue is fail-closed because its
`std::function` bodies are opaque. If it is empty, inactive function slots are
unreachable. Static debug counters/pointers and container allocator/capacity
metadata are omitted because they cannot affect a future transition. The
telemetry publishes this component list and the adapter requires it, so the
identity claim is checked against the implementation rather than inferred
from normal decision-node shape.

The reproducible runner is:

```text
PYTHONPATH=src python3 scripts/run_t079_state_utilization.py \
  --native-build /home/lsmft/stsrl-spikes/sts_lightspeed-t079-native/build-t079-py313b \
  --cohort artifacts/t070-search-v2-outcome-budget-sufficiency/reproduction-ca8da8e4183798daf3c310566ede74daf90822aa/budget-subset/t070-budget-subset-cohort.jsonl \
  --subset-manifest artifacts/t070-search-v2-outcome-budget-sufficiency/reproduction-ca8da8e4183798daf3c310566ede74daf90822aa/budget-subset/t070-budget-subset-manifest.json \
  --checkpoint artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt \
  --output-root artifacts/t079-battle-search-state-utilization-diagnostic/
```

Before that runner is permitted to start a budget, the real-native preflight
must be run with an explicit build directory. It imports the one module in that
directory, records its runtime path and SHA256, and fails closed if the module
is absent or is not the active `stsrl/main` descendant. It runs telemetry-off,
T070 geometry, and T079 state-on searches on all exact 16 retained records and
compares selected action/root statistics, search and terminal status,
simulator steps, policy/value callback counts, and geometry. The same artifact
records the T078 restore fingerprint result for those 16 records.

```text
PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t079-native/build-t079-py313b:src \
  /home/lsmft/stsrl-spikes/py313-torch/bin/python scripts/run_t079_preflight.py \
  --native-build /home/lsmft/stsrl-spikes/sts_lightspeed-t079-native/build-t079-py313b \
  --cohort artifacts/t070-search-v2-outcome-budget-sufficiency/reproduction-ca8da8e4183798daf3c310566ede74daf90822aa/budget-subset/t070-budget-subset-cohort.jsonl \
  --subset-manifest artifacts/t070-search-v2-outcome-budget-sufficiency/reproduction-ca8da8e4183798daf3c310566ede74daf90822aa/budget-subset/t070-budget-subset-manifest.json \
  --checkpoint artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt \
  --output artifacts/t079-battle-search-state-utilization-diagnostic/preflight.json
```

`run_t079_state_utilization.py` requires that passing artifact, checks its
frozen input hashes and active native commit again, and refuses to launch any
S100/S400/S1600 workers otherwise. The preflight is a gate, not a substitute
for the stage reports: each stage retains every per-call state/geometry row,
explicit `call_role` (`first_root` or `continuation`), controller provenance,
worker PID, interval, and measured peak overlap.

The runner verifies the published T070 subset manifest/cohort and T043
checkpoint hashes before starting any simulator stage. It writes one compact
stage report per budget, first-root prefix evidence, all-search-call reductions,
the precommitted classification, and a retention manifest. Raw canonical hidden
state payloads are not retained.

## Native lineage and active build input

The accepted T078 repair is native commit
`cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083`. The T079 native implementation was
rebased onto it as `c740aea2d4def6887d62461e721c8d184bc259c9`. It was promoted
to the active integration ref, not retained as a build input on a temporary
work branch. The remote `lsmfttb/sts_lightspeed` ref
`refs/heads/stsrl/main` resolves to
`1555348535d66e3035aac80933a60949d4bd850f`; that merge has `2c75d34...`,
`c740aea2...`, and `cc40c8cc...` as ancestors and is the commit recorded by the
STSRL source manifest. The earlier active merge `7b82d2ce...` is superseded by
this completeness descendant. The earlier incorrect attempt `cc8977f5d897093a63cf77df8c04aac3b24d0461`
and its old active merge `c98abea82634603c90701201fee1ecca738c2a33` are
superseded and are not accepted manifest inputs. T077 accepts only the
historical `cc40...` lineage or the active `stsrl/main` descendant; it has no
temporary-branch exception.

Classification medians are literal 16-sample medians: after sorting, the values
at zero-based indices 7 and 8 are averaged. Non-prefix records never receive
fabricated marginal-yield values; incomplete threshold inputs remain
`AMBIGUOUS`.
