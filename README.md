# sts-combat-rl

`sts-combat-rl` is currently a minimal communication probe for a future Slay the Spire combat RL project.

The current scope is intentionally small:

- read JSON states from a CommunicationMod-style external process;
- parse enough state to identify combat, player fields, hand cards, monsters, energy, turn, and screen type;
- choose a simple scripted action;
- log raw state, parsed summaries, and emitted commands for debugging.
- define a thin simulator adapter contract for future fast simulator spikes.

This stage does not implement reinforcement learning, a Gymnasium environment, Stable-Baselines3 integration, action masks, or Slay the Spire game mechanics.

The first agent target is battle-only. Non-combat screens can be advanced by a
separate non-combat driver, but map/reward/shop/event navigation is not part of
the current trainable agent contract.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Mock Run

```bash
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
```

This reads a local fixture, parses it, applies the scripted policy, and prints only the command string to stdout.

## stdin/stdout Mode

```bash
python -m sts_combat_rl.cli
```

In default mode, the probe reads one JSON object per stdin line and writes one command per stdout line. Debug information is written to `logs/sts_combat_rl.log` by default so stdout stays clean for the game protocol.

At startup, stdin/stdout mode first writes `ready_for_command` to stdout. CommunicationMod uses this as its external-process handshake before sending game state.

To capture real stdin samples during CommunicationMod calibration, append raw non-empty input lines to a local JSONL file:

```bash
python -m sts_combat_rl.cli --capture-file tests/fixtures/real_samples/captured.jsonl
```

The capture file is written separately from stdout. Each received input line is saved before parsing, so malformed samples can still be inspected later.

For live CommunicationMod testing, prefer fresh per-session files instead of appending every run to one fixed file:

```bash
python -m sts_combat_rl.cli --capture-dir tests/fixtures/real_samples --log-dir logs/communicationmod-live
```

For manual sample capture, add `--manual`. In this mode the probe never emits
gameplay actions such as `play`, `end`, `choose`, `proceed`, or `potion`; it only
uses `wait`/`state` polling while you control the game:

```bash
python -m sts_combat_rl.cli --manual --capture-dir tests/fixtures/real_samples --log-dir logs/communicationmod-live
```

On Windows, the `config.properties` value needs escaped drive separators, for example:

```properties
command=python -m sts_combat_rl.cli --capture-dir D\:/DeadlycatCoding/STSRL/tests/fixtures/real_samples --log-dir D\:/DeadlycatCoding/STSRL/logs/communicationmod-live
runAtGameStart=true
```

Manual capture configuration:

```properties
command=python -m sts_combat_rl.cli --manual --capture-dir D\:/DeadlycatCoding/STSRL/tests/fixtures/real_samples --log-dir D\:/DeadlycatCoding/STSRL/logs/communicationmod-live
runAtGameStart=true
```

`--capture-file` intentionally appends to the named file. `--capture-dir` creates a new `capture_*.jsonl` file for each process.

Captured samples can be replayed offline without launching the game:

```bash
python -m sts_combat_rl.cli --analyze-samples tests/fixtures/real_samples/captured.jsonl
```

`--analyze-samples` accepts one or more `.jsonl` files or directories. Directory
arguments are expanded to `*.jsonl` files recursively:

```bash
python -m sts_combat_rl.cli --analyze-samples tests/fixtures/real_samples
```

This prints a parser/policy/protocol summary to stderr and keeps stdout empty.
The report includes observed screens, command sets, raw JSON keys, room types,
choice labels, monster/card/potion shapes, and a conservative `sample requests`
section for remaining protocol-calibration gaps.

The clean calibration samples currently checked by pytest are:

```text
tests/fixtures/real_samples/capture_20260603_125604_6376.jsonl
tests/fixtures/real_samples/capture_20260603_160306_27436.jsonl
tests/fixtures/real_samples/capture_20260603_161408_20736.jsonl
```

Together they cover Ironclad combat, map, rewards, shop, event, grid, rest,
chest, elite, Act 1 boss, boss reward, Act 2, Act 3, Act 4, Corrupt Heart,
victory, multi-monster, potion-state, and game-over states.

## Command Format

Command formatting is centralized in `src/sts_combat_rl/comm/protocol.py`.

The current CommunicationMod-calibrated format is:

- `start <player_class> [ascension_level] [seed]` for starting runs from the main menu.
- `play <card_index_1_based> <monster_index_0_based>` for targeted cards;
- `play <card_index_1_based>` for untargeted cards;
- `end` for ending the turn.
- `choose <choice_index_or_name>` for screen choices.
- `proceed` for the right-side proceed/confirm button.
- `return` for the left-side return/skip/cancel/leave button.
- `potion use|discard <potion_slot> [monster_index_0_based]` for potions.
- `key <key_name> [timeout_frames]` for mapped game keys.
- `click left|right <x> <y> [timeout_frames]` for screen coordinates.
- `wait <frames>` for waiting until a state change or timeout.
- `state` for requesting the current state.

Command availability is read from each CommunicationMod state through `available_commands`; when the scripted action is not currently allowed, the probe prefers `wait 30` and then `state` instead of forcing an invalid command.

The scripted policy still only uses play/end/wait/state automatically. The
other documented formats are centralized for future calibration and tests, not
for autonomous non-combat navigation yet.

## Simulator Adapter Boundary

`src/sts_combat_rl/sim/contract.py` defines the current simulator-side boundary:

- `reset(seed) -> SimulatorSnapshot`
- `legal_actions(snapshot) -> Sequence[SimulatorAction]`
- `step(action) -> SimulatorTransition`

This is only a contract for future `sts_lightspeed`-style adapters. It does not
implement a simulator, game mechanics, Gymnasium, or RL training.

`src/sts_combat_rl/sim/lightspeed.py` contains an optional wrapper for an
external patched `slaythespire.StepSimulator` module. It is import-safe for this
repo because `slaythespire` is only imported when `LightSpeedAdapter` is
constructed.

`src/sts_combat_rl/sim/features.py` provides fixed-size numeric encoders for
patched `sts_lightspeed` battle snapshots and current legal actions. This is a
pre-RL adapter utility only; it does not create a Gymnasium environment, action
mask, policy, replay buffer, or trainer.

The current battle snapshot encoder is a version-1 calibration shape with 272
features. Keep it stable while simulator/live-sample alignment is being tested;
future feature engineering should be introduced as a new encoder version rather
than silently changing this baseline.

The external `sts_lightspeed` spike patch artifacts are kept in:

```text
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
```

The patched shim exposes `reset`, `legal_actions`, `step`, a 412-value run-level
observation, and raw battle snapshot details for player, hand, monsters,
potions, and pile sizes. These fields are for simulator/live-game calibration;
the first fixed-size encoder is available, but it is not yet validated as a
final training observation.

If the patched external `slaythespire` module is on `PYTHONPATH`, run a bounded
simulator smoke calibration with:

```bash
python -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 0 --sim-steps 200
```

The report is written to stderr and stdout stays empty. The smoke chooses
non-potion actions for calibration, because initial Ironclad training will ignore
potions.

The no-potion behavior is configured through `ActionSpaceConfig`, not hard-coded
into the adapter or feature encoders. Rollout data still records all legal
actions and marks which indices are eligible for the current pass. To smoke-test
the rollout data shape:

```bash
python -m sts_combat_rl.cli --lightspeed-rollout-smoke --sim-seed 1 --sim-ascension 0 --sim-steps 200
```

To include potion-related actions in these simulator smokes later, add
`--include-potions`.

To collect several rollout smokes and validate the framework-neutral batch
shape:

```bash
python -m sts_combat_rl.cli --lightspeed-batch-smoke --sim-seed 1 --sim-rollouts 3 --sim-steps 200
```

The decision batch keeps variable-length legal-action lists. It does not impose
a fixed action mask or a specific RL framework interface.

To smoke-test the next policy/model boundary without training anything:

```bash
python -m sts_combat_rl.cli --lightspeed-policy-smoke --sim-seed 1 --sim-rollouts 3 --sim-steps 200
```

This builds the same decision batch, then applies a framework-neutral
legal-action-index policy. Available smoke policies are `preferred-kind`,
`first-eligible`, `replay-chosen`, and `random-eligible` through
`--sim-policy`. Policy smoke reports are stderr-only and keep stdout empty.

To drive one bounded simulator rollout through the same policy interface:

```bash
python -m sts_combat_rl.cli --lightspeed-policy-rollout-smoke --sim-seed 1 --sim-steps 200
```

This is still only a smoke collector. It verifies that online policy selection
can choose legal-action indices from the encoded candidate list before any
trainer or RL framework is introduced.

To run a small pre-training episode evaluation through the same policy boundary:

```bash
python -m sts_combat_rl.cli --lightspeed-episode-eval --sim-seed 1 --sim-episodes 10 --sim-steps 200
```

This reports episode count, terminal outcomes, collected steps, final floors,
chosen action kinds, and a narrow `outcome_value` calibration signal: terminal
victory is `+1`, terminal loss is `-1`, and unfinished/unknown outcomes are `0`.
It is an evaluation smoke only; it does not add a trainer, replay buffer, RL
algorithm, or environment wrapper. `replay-chosen` is only valid for offline
`--lightspeed-policy-smoke`; online rollout/evaluation policies must choose from
the current encoded candidate list.

For the current battle-agent phase, prefer the battle-only sweep:

```bash
python -m sts_combat_rl.cli --lightspeed-battle-sweep --sim-seed 1 --sim-episodes 10 --sim-steps 200
```

This uses the selected policy only on `BATTLE` states. Non-combat states are
advanced by a separate non-combat driver and reported separately, so the
battle-agent data path can be calibrated without treating route/reward/shop
choices as agent decisions. For battle-agent smokes the default non-combat
driver is seeded `random-eligible`; use `--sim-non-combat-policy preferred-kind`
or `first-eligible` for deterministic comparisons.

To validate the battle-only decision batch that a future trainer would consume:

```bash
python -m sts_combat_rl.cli --lightspeed-battle-batch-smoke --sim-seed 1 --sim-episodes 10 --sim-steps 200
```

This builds a framework-neutral `DecisionBatch` from battle-agent decisions only.
Non-combat driver decisions are counted as excluded steps and are not included
as training examples. This still does not define rewards or run training.

To calibrate battle episode boundaries before choosing a reward function:

```bash
python -m sts_combat_rl.cli --lightspeed-battle-segments-smoke --sim-seed 1 --sim-episodes 10 --sim-steps 200
```

This identifies contiguous battle-agent-controlled segments, reports whether
each segment ended in a non-terminal battle exit, terminal loss/victory, or was
truncated by the step limit, and summarizes available fields such as battle
decision count and HP delta. It does not choose the final reward.

To inspect raw reward-component candidates before choosing reward weights:

```bash
python -m sts_combat_rl.cli --lightspeed-battle-reward-components --sim-seed 1 --sim-episodes 10 --sim-steps 200
```

This reuses the same battle-agent/non-combat-driver split and reports raw
components such as battle-success proxy, terminal loss, HP delta/loss/gain,
decision count, max-HP delta, gold delta, and potion-count delta when both ends
of the battle segment expose the field. It also reports future signal gaps such
as relic counters and post-combat deck/reward deltas. It does not assign reward
weights, run RL, or define a Gymnasium environment.
Segments with resource deltas, terminal losses/victories, truncation, or HP gain
are highlighted for inspection; use `--reward-detail-limit 0` to hide details or
raise the limit for a longer drilldown.

To check whether real CommunicationMod combat captures fit the same fixed-size
feature shape, run:

```bash
python -m sts_combat_rl.cli --calibrate-combat-features tests/fixtures/real_samples
```

This also writes only to stderr. It reports feature length, hand/monster shapes,
and field coverage for the first pre-RL encoder.

## Logs

By default, logs are written to:

```text
logs/sts_combat_rl.log
```

Use `--log-file` to change the path:

```bash
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json --log-file logs/mock.log
```

## TODO

- Expand CommunicationMod command coverage beyond combat probe commands.
- Keep recording real Ironclad JSON samples across screens and edge cases.
- Expand the parser with observed state variants.
- Keep simulator work behind a thin adapter spike until reset/legal_actions/step
  are proven.
- Defer Gymnasium, action masking, and RL integration until after the simulator
  feature contract is calibrated against enough simulator/live-game states.
- Treat potion commands and CommunicationMod error captures as optional
  follow-up calibration, not blockers for the first simulator-backed training
  pass.
- Keep action-space filtering configurable so adding potions later does not
  require changing simulator adapters, feature shapes, or rollout records.
- Keep rollout batching framework-neutral: preserve all legal actions and
  eligible indices so future RL implementations can choose their own masking or
  variable-action scorer.
- Keep policy/model selection framework-neutral: choose legal-action indices
  from variable candidate lists before introducing any trainer or RL library.
- Add only pre-training simulator episode statistics until outcome/progress
  fields are calibrated well enough to choose a training interface.
- Keep the first trainable target battle-only; non-combat progression can stay
  scripted until a separate run-management agent is explicitly in scope.
