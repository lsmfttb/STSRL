# sts-combat-rl

Battle-agent research infrastructure for Slay the Spire.

The project uses the external `sts_lightspeed` simulator as the authoritative
game implementation. This repository owns controller boundaries, search and
policy experiments, dataset construction, artifact migration, training, and
evaluation. It does not reimplement game mechanics.

The current trainable scope is battle decisions. Non-combat decisions are made
by a separately named, seeded stochastic driver so complete runs can generate
realistic and diverse battle-start states. The final target is A20 Heart
victory.

## Read First

- [`docs/current_status.md`](docs/current_status.md): what works now, known
  limitations, and immediate priorities.
- [`docs/project_architecture.md`](docs/project_architecture.md): authoritative
  repository-wide design contract.
- [`docs/battle_dataset_search_and_sl_plan.md`](docs/battle_dataset_search_and_sl_plan.md):
  active dataset, search-agent, and SL-branch roadmap.
- [`docs/normal_information_search_and_resource_value_plan.md`](docs/normal_information_search_and_resource_value_plan.md):
  normal-information search and continuation-value design.
- [`docs/sts_lightspeed_wsl_spike.md`](docs/sts_lightspeed_wsl_spike.md):
  current WSL simulator setup and verification commands.
- [`docs/README.md`](docs/README.md): complete documentation map and authority
  rules.

Historical investigations and superseded plans live under
[`docs/history/`](docs/history/README.md). They are not current contracts.

## Current Architecture

```text
external sts_lightspeed simulator
        |
        v
simulator adapter and sanitized decision context
        |
        v
explicit battle controller + explicit non-combat driver
        |
        v
controlled complete-run executor
        |
        +--> natural battle-start pools
        +--> fixed/stratified evaluation
        +--> search-teacher datasets
        +--> policy/value training
```

The current native `BattleScumSearcher2` copies hidden simulator state and is
therefore an Oracle-like baseline, not a normal-information search agent.
Search remains the primary battle-policy direction; learned models are expected
to guide or accelerate search rather than automatically replace it.

## Boundaries

- `sts_lightspeed` owns game rules and authoritative state transitions.
- Real simulator gates run through WSL, not Windows Python.
- Normal-information agents receive only player-visible information.
- Battle and non-combat controllers always have explicit, complete provenance.
- Natural, stratified-training, constructed, paired-counterfactual, Oracle,
  normal-information, and SL-enabled results remain separately tagged.
- A0 is allowed for debugging or curriculum, but A20 is the final target and
  ascension remains explicit.
- Gymnasium, Stable-Baselines3, vendored game files, and local game-mechanics
  implementations are out of scope.

See [`AGENTS.md`](AGENTS.md) for the concise contributor rules.

## Install

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Optional PyTorch training dependencies:

```powershell
pip install -e ".[dev,train]"
```

## Local Checks

```powershell
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Use `python -m sts_combat_rl.cli --help` for the complete command surface.

## WSL Simulator

The patched external checkout and builds are expected at:

```text
~/stsrl-spikes/sts_lightspeed
~/stsrl-spikes/sts_lightspeed/build-py
~/stsrl-spikes/sts_lightspeed/build-py313-final
~/stsrl-spikes/py313-torch
```

Run a bounded simulator smoke from Windows:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
```

Run the checkpoint determinism gate:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-checkpoint-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --checkpoint-replay-steps 200 --log-file -"
```

More WSL commands and patch details are in
[`docs/sts_lightspeed_wsl_spike.md`](docs/sts_lightspeed_wsl_spike.md).

## Main Workflows

Collect a natural battle-start pool:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-jsonl artifacts/battle_start_pool/natural_a20.jsonl --sim-seed 1 --sim-episodes 100 --sim-ascension 20 --sim-steps 400 --log-file -"
```

Freeze a deterministic structural evaluation cohort:

```powershell
python -m sts_combat_rl.cli --battle-start-pool-freeze-eval INPUT_POOL.jsonl FIXED_EVAL.jsonl --eval-per-stratum 3 --log-file -
```

Collect search-teacher data from a pool:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-search-dataset-from-pool INPUT_POOL.jsonl OUTPUT_SEARCH.jsonl --search-pool-battles 500 --search-pool-balanced-fraction 0.5 --search-simulations 100 --sim-steps 400 --log-file -"
```

Artifact-producing commands must preserve complete controller provenance.
Smoke-scale data validates plumbing only; it is not evidence that a model is
strong or ready for broad training.

## State And Objective

The tactical battle representation includes explicit ascension, player state,
card instances and piles, monsters and move state, relics and visible counters,
potions, and legal-action details.

The long-term context target is broader:

- the complete player-visible run history, including prior rooms, events,
  rewards, shops, rests, battles, and visible choices;
- the complete currently visible map, current node, and available routes;
- the visible Act Boss;
- persistent deck, relic, potion, gold, key, HP, max-HP, and visible counter
  state.

The current implementation preserves only part of that target, especially
encounter history and visible route context. See `docs/current_status.md` for
the exact gap.

Battle-end resources remain structured outcomes. They are not permanently
collapsed into fixed hand-written reward weights. The intended long-term value
is their context-dependent contribution to A20 Heart victory.

## Data And Legacy

Current writers emit only current artifact schemas. Readers migrate legacy
artifacts sequentially and report information that old versions cannot recover.
Do not infer missing provenance.

Generated artifacts belong under the ignored `artifacts/` directory. Do not
commit game files, simulator binaries, save files, large datasets, or model
checkpoints.

## Collaboration

The current integration line is `codex/integration-current`. Create focused
`codex/<topic>` task branches from it; do not use a dirty `main` worktree for
parallel development. The task model commits its work, then the integration
owner reviews behavior, tests, provenance, documentation impact, and migration
compatibility, runs the required gates, and merges it.
