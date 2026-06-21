# sts_lightspeed WSL Operations

This guide lists simulator operations available on the latest `main`.
Checkpoint verification and portable battle-start pools are current
capabilities. Search and fixed evaluation remain task-scoped future work.

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
patches/sts_lightspeed_checkpoint_restore.patch
patches/sts_lightspeed_battle_start_metadata.patch
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_non_combat_potion_actions.patch
patches/sts_lightspeed_gcc15_compat.patch
```

The canonical base is external commit `7476a81`. The patch order and a clean
GCC 15 build gate are kept in `scripts/verify_lightspeed_patch_stack.sh`:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_patch_stack.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

The verifier uses a disposable worktree and does not replace `build-py`.
Apply the same ordered stack and rebuild the system build before using the
runtime gates below. Do not treat an older `build-py` as supporting checkpoint
or completed-battle-outcome fields just because the Python branch is current.

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

### Tactical Feature Contract Audit

Run this only after rebuilding `build-py` from the current verified patch stack.
It validates required simulator projections, reports schema/version, unknown
identities, missing fields, and simulator/live field parity. It is not a
live-controller smoke.

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-tactical-feature-audit --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
```

Captured CommunicationMod data can be checked against the same contract without
launching the simulator:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --audit-tactical-features tests/fixtures/real_samples --log-file -"
```

### Native Battle-Start Checkpoint Determinism

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-checkpoint-verify --sim-seed 1 --sim-ascension 20 --sim-steps 200 --checkpoint-replay-steps 10 --log-file -"
```

### Natural Battle-Start Pool And Fresh Restore

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && mkdir -p artifacts/checkpoints && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool artifacts/checkpoints/a20_seed1_3.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --battle-start-sample-count 20 --log-file - && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-restore artifacts/checkpoints/a20_seed1_3.jsonl --sim-seed 1 --sim-ascension 20 --log-file -"
```

The manifest excludes native checkpoint payloads. The restore command creates
fresh adapters and replays the recorded source seed and public action
identities; it must not be presented as cross-process native-checkpoint
serialization.

## Troubleshooting

- Import failures usually mean the selected Python version does not match the
  pybind build directory.
- stdout is reserved for protocol output. Use `--log-file -` for diagnostics.
- A command documented only in a future task is not expected to exist on
  `main`.

See [`current_status.md`](current_status.md) for current implementation truth
and [`experiment_log.md`](experiment_log.md) for historical evidence.
