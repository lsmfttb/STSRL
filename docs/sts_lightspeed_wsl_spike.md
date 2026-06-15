# sts_lightspeed WSL Operations

This guide lists simulator operations available on the latest `main`. Planned
checkpoint, pool, search, and evaluation commands remain in their task
specifications until merged.

## Boundary

The authoritative simulator checkout stays outside this repository:

```text
~/stsrl-spikes/sts_lightspeed
```

This repository stores Python adapters and reproducible source patches. It does
not vendor simulator binaries, game files, saves, or game mechanics.

Real simulator gates run through WSL, not Windows Python.

## Current Environment

```text
external checkout: ~/stsrl-spikes/sts_lightspeed
system build:      ~/stsrl-spikes/sts_lightspeed/build-py
repository in WSL: /mnt/d/DeadlycatCoding/STSRL
```

## Patches Present On Main

```text
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
```

The current patch surface supports controlled reset, legal-action enumeration,
stepping, and snapshots for the existing simulator and battle-agent data
smokes.

Additional patches preserved in legacy commit `d56e10e` are not current
capabilities. They are mapped to focused tasks in [`tasks/`](tasks/README.md)
and must be reviewed independently before entering `main`.

## Common WSL Prefix

From Windows PowerShell:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli ..."
```

## Current Gates

### Basic Simulator Smoke

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
```

### Bounded Battle Sweep

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-sweep --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

### Training-Readiness Plumbing Smoke

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-training-readiness --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

This gate validates current data plumbing only. It does not train a model or
demonstrate agent strength.

## Troubleshooting

- Import failures usually mean the selected Python version does not match the
  pybind build directory.
- stdout is reserved for protocol output. Use `--log-file -` for diagnostics.
- A command documented only in a future task is not expected to exist on
  `main`.

See [`current_status.md`](current_status.md) for current implementation truth
and [`experiment_log.md`](experiment_log.md) for historical evidence.
