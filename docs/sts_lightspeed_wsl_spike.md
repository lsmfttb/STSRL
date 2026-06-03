# sts_lightspeed WSL Spike

This spike stays outside the repository working tree under:

```text
~/stsrl-spikes/sts_lightspeed
```

## Clone Result

Cloned GitHub commit:

```text
7476a81
```

Repository:

```text
https://github.com/gamerpuppy/sts_lightspeed
```

License:

```text
MIT
```

## Project Shape

The repository is a real C++ simulator codebase, not a skeleton:

```text
apps/
bindings/
include/
src/
json/
pybind11/
```

First-party source size from the WSL checkout is roughly 34k lines across
`include`, `src`, `apps`, and `bindings`.

The README claims:

- C++17 standalone simulator.
- Designed to be RNG accurate.
- Console-playable.
- 1M random playouts in 5s with 16 threads.
- Save-file loading, with loading into combat currently supported.
- Tree search.
- All enemies, all relics, all Ironclad cards, all colorless cards, and
  everything outside combat/all acts.

## Python Binding Surface

`bindings/slaythespire.cpp` defines a `pybind11` module named `slaythespire`.
Observed bindings include:

- `play(...)`
- `get_seed_str(...)`
- `get_seed_long(...)`
- `getNNInterface()`
- `Agent`
- `GameContext(CharacterClass, seed, ascension)`
- `GameContext.pick_reward_card(index)`
- `GameContext.skip_reward_cards()`
- `GameContext.get_card_reward()`
- `GameContext.deck`
- `GameContext.relics`
- `SpireMap`
- `Card`
- enums such as `GameOutcome`, `ScreenState`, `CharacterClass`, and `Room`

This is the strongest current candidate for a fast simulator adapter.

## Build Result

After installing the WSL toolchain, the external checkout builds far enough to
validate it as the primary simulator candidate.

Observed toolchain:

```text
c++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0
python3 3.14.x
```

Two external-checkout-only workarounds were needed:

1. Pass `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` because the bundled `json`
   subproject declares an old CMake policy version.
2. Compile with `-include algorithm` because GCC 15 exposes missing
   `<algorithm>` includes in the current source.

The bundled `pybind11` checkout also needed to be moved from the old bundled
version to `v3.0.4` inside the external spike checkout. The old pybind11 version
does not compile against WSL's Python 3.14 headers.

Validated build targets:

```text
small-test: built and ran successfully
slaythespire pybind module: built and imported successfully
```

The C++ `small-test` target printed a generated map/path and exited cleanly.

## Python Probe Result

Importing the WSL-built module with `PYTHONPATH=build-py` worked:

```text
module: slaythespire
doc: pybind11 example plugin
seed sample: get_seed_str(1) -> 1
GameContext(CharacterClass.IRONCLAD, 1, 0):
  act=1
  floor_num=0
  cur_hp=80
  max_hp=80
  screen_state=EVENT_SCREEN
NNInterface.getObservation(...):
  length=412
  first values=[80, 80, 99, 0, 1, 0, 0, 0, 0, 0]
```

Known binding issue:

```text
NNInterface.observation_space_size raises a TypeError because the exposed
property/function signature is wrong.
```

Built-in `Agent.playout(...)` works. With `simulation_count_base=1` and
`boss_simulation_multiplier=1`, a 20-run smoke benchmark completed at roughly
4k-6k playouts/second on this WSL machine, with all 20 smoke runs losing between
floor 4 and floor 16. This is only a binding smoke test, not a final training
throughput benchmark.

The exposed Python module does not currently include a direct controlled
step/action API. Observed top-level bindings were:

```text
Agent, Card, CardColor, CardId, CardRarity, CardType, CharacterClass,
GameContext, GameOutcome, MonsterEncounter, NNInterface, Relic, RelicId, Room,
ScreenState, SpireMap, getNNInterface, get_seed_long, get_seed_str, play
```

No action-related Python symbols were exposed.

## Step Shim Spike

A temporary external-checkout pybind shim was added to
`bindings/slaythespire.cpp`. It is not vendored into this repository.

External checkout diff summary:

```text
bindings/slaythespire.cpp | 526 insertions
pybind11                  | submodule moved to v3.0.4 for Python 3.14
```

New Python symbols from the shim:

```text
LightSpeedAction
StepSimulator
```

`StepSimulator` owns both:

- `GameContext`, for map/event/reward/rest/shop state.
- `BattleContext`, initialized lazily when `GameContext.screenState` becomes
  `BATTLE`.

Exposed methods:

```text
snapshot() -> dict
observation() -> list[int]
legal_actions() -> list[LightSpeedAction]
step(action: LightSpeedAction) -> dict
reset(CharacterClass, seed, ascension) -> None
```

The shim snapshot now exposes enough battle-state metadata to compare simulator
states against CommunicationMod captures before any training work:

```text
battle_player
battle_hand
battle_monsters
battle_potions
battle_draw_pile_size
battle_discard_pile_size
battle_exhaust_pile_size
```

The detailed battle fields come directly from `BattleContext`, `CardInstance`,
`Monster`, and `Player`. They are debug/raw adapter data, not a hand-written game
mechanic model.

The shim uses existing simulator logic only:

- non-combat actions use `GameAction::getAllActionsInState(...)`,
  `GameAction::isValidAction(...)`, and `GameAction::execute(...)`;
- battle actions use `Action::isValidAction(...)`, `Action::execute(...)`, and
  `Action::enumerateCardSelectActions(...)`;
- when a `BattleContext` reaches a terminal battle outcome,
  `BattleContext::exitBattle(GameContext&)` writes the result back to
  `GameContext`.

Smoke result:

```text
initial screen: EVENT_SCREEN
observation length: 412
reached first BATTLE at step 4
first battle legal actions: 5 card actions + 1 end_turn action
executed end_turn successfully
250-step naive loop: crossed battle exits and reached PLAYER_LOSS at floor 13
invalid action failures: none observed
snapshot probe: battle_hand/battle_monsters/battle_player/pile sizes/potions
                are visible from Python and update after a card action
```

Known limitations:

- `GameAction::printDesc(...)` is empty upstream, so non-combat action labels are
  coarse `kind/bits/idx` labels.
- `NNInterface.getObservation(...)` is still run-level only; the battle details
  currently live in `snapshot().raw` rather than a final numeric training
  observation.
- The shim is still an external spike, not a committed dependency or vendored
  simulator.
- No RL, Gymnasium, Stable-Baselines3, or local game mechanics were added.

The reproducible patch artifacts are stored in this repository under:

```text
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
```

The repository-side `sts_combat_rl.sim.features` module can turn these raw
snapshot/action fields into stable-size numeric vectors for future algorithm
work. That encoder is intentionally separate from the external C++ patch and
does not add Gymnasium, action masks, trainers, or local game mechanics.

The repository CLI also has a bounded smoke command for this patched module:

```text
python -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 0 --sim-steps 200
```

The smoke reports observation/action/feature sizes to stderr and uses a
deterministic non-potion action selector for calibration. This is deliberately
not a training policy.

Bounded rollout-data smoke:

```text
python -m sts_combat_rl.cli --lightspeed-rollout-smoke --sim-seed 1 --sim-ascension 0 --sim-steps 200
```

The rollout records all legal action features plus eligible action indices. The
default `ActionSpaceConfig` excludes potion-related actions for the first pass;
`--include-potions` switches the same pipeline to include them.

Framework-neutral batch smoke:

```text
python -m sts_combat_rl.cli --lightspeed-batch-smoke --sim-seed 1 --sim-rollouts 3 --sim-steps 200
```

The batch format keeps variable legal-action lists instead of choosing a Gym,
SB3, or torch-specific representation at this phase.

The live CommunicationMod side can be checked against the same feature shape
with:

```text
python -m sts_combat_rl.cli --calibrate-combat-features tests/fixtures/real_samples
```

Use clean capture files for readiness decisions; older mixed live logs can still
be useful for error-regression checks but should not drive feature calibration.

## Next Adapter Spike

Do not add RL or Gymnasium yet. After a successful shim smoke, the next spike
should:

- decide whether to keep the shim as a local patch, a fork branch, or an upstream
  patch proposal;
- improve non-combat action labels if needed for CommunicationMod mapping;
- calibrate the first stable numeric battle/action feature contract against
  simulator states and CommunicationMod captures;
- keep potion actions out of the first training pass unless later calibration
  proves they are worth adding;
- keep potion support as an action-space configuration instead of deleting
  potion features or action metadata;
- keep rollout batches framework-neutral until the first training algorithm is
  chosen;
- avoid Gymnasium, Stable-Baselines3, RL training loops, and any local
  reimplementation of game mechanics.
