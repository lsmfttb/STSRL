# decapitate-the-spire WSL Spike

> Historical simulator investigation. It is not part of the current runtime.

This spike stays outside the repository working tree under:

```text
~/stsrl-spikes/decapitate-the-spire
```

## Clone Result

Cloned GitHub commit:

```text
7a7b7ff
```

The package has no install requirements in `setup.py`, so it can be smoke-tested
directly with:

```bash
cd ~/stsrl-spikes/decapitate-the-spire
PYTHONPATH=. python3 <script.py>
```

## API Surface Observed

Relevant objects found in `decapitate_the_spire/game.py`:

- `Game(create_player, create_dungeon)`
- `Game.step(action) -> (reward, is_terminal, info)`
- `Game.generate_action_mask() -> list[list[bool]]`
- `Game.is_action_valid(action)`
- `ActionGenerator`
- `TheSilent`
- `MiniDungeon`
- `Exordium`

The action space is two-dimensional:

- dimension 0: end turn, hand card slots, potion use slots, potion discard slots
- dimension 1: monster target slots plus a no-target sentinel

This maps roughly to CommunicationMod concepts such as play card, target, end
turn, choose, proceed, potion, and discard potion.

## Smoke Result

Creating a game and advancing with explicit legal actions worked:

```text
initial_request SimpleChoiceEventRequest
initial_valid [(1, 5), (2, 5)]
pick_neow_reward(True): valid
request FirstPathChoiceRequest
pick_first_path(0): valid
request CombatActionRequest
```

A naive first-legal-action loop:

```text
steps 10
terminal True
last_info {'win': False}
steps_per_second 2637.2
```

The policy lost quickly, but the smoke confirms that reset/create, action masks,
legal stepping, and terminal output exist and are fast enough for a simulator
adapter experiment.

## Risks

- GPLv3 license.
- Pre-alpha project status.
- PyPI latest release is 0.2.0 from 2021.
- Only Silent is marked implemented.
- Exordium content is incomplete.
- Correctness relative to the real game is not guaranteed.

## Next Adapter Spike

Do not add Gymnasium, Stable-Baselines3, deep-learning frameworks, or local game
mechanics here. Any future code change should be a small optional adapter
module, guarded so this repository does not import `decapitate_the_spire` unless
the package is explicitly available.

Minimal adapter goals:

- create/reset `Game(TheSilent, MiniDungeon)`
- expose valid action coordinates from `generate_action_mask()`
- convert a simulator state into a compact debug summary
- step a provided legal action
- benchmark N random/legal steps
