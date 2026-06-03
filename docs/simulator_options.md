# Simulator Options

This project should keep CommunicationMod as a live-game calibration and smoke-test
path. RL training needs a fast headless simulator or a simulator adapter; the
real game loop is too slow and too stateful for high-throughput rollouts.

## Current Recommendation

Use `sts_lightspeed` as the primary simulator candidate:

- Repository: https://github.com/gamerpuppy/sts_lightspeed
- License: MIT
- Shape: C++17 standalone simulator with pybind11 bindings, console app, and
  tree-search tooling
- Finding: cloned commit `7476a81`; first-party source is roughly 34k lines and
  includes `src`, `include`, `apps`, and `bindings`
- Build result: WSL build succeeded for the C++ `small-test` target and the
  Python `slaythespire` pybind module after external-checkout-only fixes for
  CMake policy compatibility, GCC 15 `<algorithm>` includes, and pybind11/Python
  3.14 compatibility
- Probe result: Python can create `GameContext`, read a 412-value observation
  from `NNInterface`, and run built-in `Agent.playout(...)`
- Step shim result: a temporary external pybind `StepSimulator` shim can expose
  `snapshot`, `observation`, `legal_actions`, and `step` by wrapping existing
  `GameAction`, `Action`, and `BattleContext` APIs
- Snapshot result: the shim now exposes raw battle details from the native
  `BattleContext`, including player, hand, monsters, potions, and pile sizes
- Feature result: `sts_combat_rl.sim.features` can encode patched battle
  snapshots and current legal actions into stable-size numeric vectors without
  adding Gymnasium, action masks, or RL code
- Calibration result: `python -m sts_combat_rl.cli --lightspeed-smoke` can run a
  bounded simulator smoke, summarize observation/action/feature sizes, and avoid
  choosing potion actions
- Rollout result: `python -m sts_combat_rl.cli --lightspeed-rollout-smoke`
  collects bounded rollout records with snapshot features, all legal action
  features, eligible action indices, and chosen action metadata
- Batch result: `python -m sts_combat_rl.cli --lightspeed-batch-smoke` collects
  several rollout smokes and validates a framework-neutral decision batch with
  variable legal-action lists
- Live feature result:
  `python -m sts_combat_rl.cli --calibrate-combat-features ...` can summarize
  whether CommunicationMod combat samples fit the same fixed-size feature shape
- Current blocker: the shim is still an external checkout patch, non-combat
  action labels are coarse, and the numeric feature contract still needs
  simulator/live-game calibration before training assumptions are locked
- Decision: primary candidate; continue by hardening the shim/adapter boundary

Use `decapitate-the-spire` only as the secondary fallback:

- Project page: https://pypi.org/project/decapitate-the-spire/
- License: GPLv3
- Shape: Python headless clone with a `game.step(...)` style loop
- Finding: cloned GitHub commit `7a7b7ff`; source imports without installation,
  exposes `Game`, `ActionGenerator`, `generate_action_mask()`, and `step(action)`
- Smoke result: `Game(TheSilent, MiniDungeon)` advanced from Neow choice to
  combat using legal actions; a naive first-legal-action loop reached terminal
  in 10 steps at roughly 2600 steps/s on WSL
- Risk: pre-alpha, only Silent is implemented, Exordium content is incomplete,
  and correctness must be treated as approximate

Keep `CommunicationMod` and `STS-AI-Master`-style bridge approaches as live-game
calibration or architecture references, not as the preferred high-throughput
training backend.

The first `conquer-the-spire` build spike found that current master is not a
usable simulator implementation:

- Repository: https://github.com/utilForever/conquer-the-spire
- License: MIT
- Shape: C++17 Slay the Spire simulator with console/GUI programs and C++/Python APIs
- Claimed platform support: macOS, Ubuntu, Windows, and WSL
- Claimed content coverage: Ironclad, Silent, Defect, monsters, elites, bosses,
  events, relics, potions, merchant, ascension
- Finding: cloned master at `483abc9`; first-party C++ source is an `Add(int,
  int)` skeleton with no game state, step loop, or Python binding
- Decision: reject current master as a usable training simulator

For the broader candidate scan, see `docs/simulator_candidate_scan.md`.

`spirecomm` and CommunicationMod remain useful for live-game IO, but they do not
solve throughput. They should not be the primary RL environment.

## Build Spike Goals

Do not integrate RL, Gymnasium, Stable-Baselines3, or game mechanics yet.

The next simulator spike should only answer:

- Should the `sts_lightspeed` shim live as a local patch, fork branch, or
  upstream patch proposal?
- Can the action/debug surface map back to CommunicationMod command concepts?
- Does the first fixed-size Ironclad battle/action feature contract preserve the
  state needed by common combat decisions?
- Can the optional Python adapter stay import-safe when `slaythespire` is absent?
- Can first-pass Ironclad training ignore potions without destabilizing legal
  action selection, while preserving enough recorded data to add potions later?
- Which training approach should consume the variable-action decision batch:
  per-action scorer, padded action sets, or another framework-specific adapter?

For WSL-specific notes, see `docs/sts_lightspeed_wsl_spike.md`,
`docs/decapitate_the_spire_wsl_spike.md`, and
`docs/conquer_the_spire_wsl_spike.md`.

## Adapter Boundary

If a simulator candidate works, introduce only a thin adapter contract first:

- `reset(seed: int | None) -> observation`
- `legal_actions(observation) -> list[action]`
- `step(action) -> transition`

Keep this contract separate from CommunicationMod. The existing parser/protocol
path should continue to cover live game calibration; the simulator path should
cover fast offline rollouts.
