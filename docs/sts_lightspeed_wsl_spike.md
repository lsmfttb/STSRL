# sts_lightspeed WSL Operations

This is the current operational guide for the external patched
`sts_lightspeed` simulator. Dated build and experiment results live in
[`experiment_log.md`](experiment_log.md). Earlier simulator comparisons live in
[`history/`](history/README.md).

## Boundary

The external checkout stays outside this repository:

```text
~/stsrl-spikes/sts_lightspeed
```

This repository stores reproducible patch files, Python adapters, controllers,
datasets, and tests. It does not vendor the simulator or reimplement game
mechanics.

Real simulator commands run through WSL, not Windows Python.

## Expected Environment

```text
external checkout: ~/stsrl-spikes/sts_lightspeed
system build:      ~/stsrl-spikes/sts_lightspeed/build-py
PyTorch build:     ~/stsrl-spikes/sts_lightspeed/build-py313-final
PyTorch Python:    ~/stsrl-spikes/py313-torch/bin/python
repository in WSL: /mnt/d/DeadlycatCoding/STSRL
```

`build-py` is used for ordinary simulator collection and gates.
`build-py313-final` plus `py313-torch` is used when WSL online inference needs
PyTorch.

## Patch Inventory

The repository currently carries:

```text
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
patches/sts_lightspeed_checkpoint_restore.patch
patches/sts_lightspeed_battle_start_metadata.patch
patches/sts_lightspeed_battle_start_transform.patch
patches/sts_lightspeed_battle_search_teacher.patch
patches/sts_lightspeed_battle_search_root_actions.patch
patches/sts_lightspeed_battle_potion_action_alignment.patch
patches/sts_lightspeed_non_combat_potion_actions.patch
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_run_resource_snapshot.patch
patches/sts_lightspeed_public_run_context.patch
```

The patches expose authoritative capabilities instead of duplicating mechanics
in Python:

- controlled reset, legal-action enumeration, stepping, and snapshots;
- native battle-start checkpoint capture and restore;
- structural battle-start metadata;
- native search root statistics;
- aligned potion actions;
- run resource snapshots;
- partial sanitized public run context.

The current public-context patch exposes visible Boss, completed encounter
history, visible map, current node, and next nodes. The project target is a
complete typed player-visible run history including events and prior public
choices; that broader capability is not implemented yet.

The battle-start transform patch can apply native transforms, but repository
policy determines whether a transform is accepted as training data. HP
construction is moving toward a conservative practical approximation;
authoritative replay certification is optional rather than a required path for
every small HP perturbation.

## Build Notes

The external checkout historically required:

- `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` for the bundled JSON subproject;
- `-include algorithm` for missing includes exposed by the WSL compiler;
- pybind11 `v3.0.4` for Python 3.14 compatibility.

Treat these as external-build details. Do not copy generated build output into
this repository.

## Common WSL Prefixes

System Python:

```text
cd /mnt/d/DeadlycatCoding/STSRL &&
PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src
python3 -m sts_combat_rl.cli ...
```

PyTorch Python:

```text
cd /mnt/d/DeadlycatCoding/STSRL &&
PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-final:/mnt/d/DeadlycatCoding/STSRL/src
/home/lsmft/stsrl-spikes/py313-torch/bin/python -m sts_combat_rl.cli ...
```

From Windows PowerShell, wrap either command with:

```powershell
wsl.exe -d Ubuntu -e bash -lc "..."
```

## Required Gates

### Basic Simulator Smoke

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
```

### Checkpoint Determinism

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-checkpoint-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --checkpoint-replay-steps 200 --log-file -"
```

This gate must compare restored initial state, legal actions, transitions, and
terminal results without reconstructing mechanics in Python.

### Battle-Start Pool Collection

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-jsonl artifacts/battle_start_pool/natural_a20.jsonl --sim-seed 1 --sim-episodes 100 --sim-ascension 20 --sim-steps 400 --log-file -"
```

Natural-pool collection uses explicit battle and non-combat controller
provenance. Deliberately collecting a policy baseline requires an explicit
controller choice.

### Pool Restore

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-restore-smoke artifacts/battle_start_pool/natural_a20.jsonl --sim-ascension 20 --pool-restore-limit 0 --log-file -"
```

### Search Interface

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-search-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --search-simulations 100 --log-file -"
```

The current native search copies hidden simulator state. Passing this gate
proves the Oracle-like search interface works; it does not prove a
normal-information search baseline.

### Fixed Battle Evaluation

Freeze a cohort offline:

```powershell
python -m sts_combat_rl.cli --battle-start-pool-freeze-eval INPUT_POOL.jsonl FIXED_EVAL.jsonl --eval-per-stratum 3 --log-file -
```

Evaluate native search through WSL:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-fixed-battle-search-eval FIXED_EVAL.jsonl --sim-ascension 20 --search-simulations 20 --search-selection-rule highest-mean --sim-steps 400 --log-file -"
```

## Adapter Expectations

The Python adapter exposes framework-neutral snapshots, variable legal-action
lists, transitions, checkpoint operations, and search results. It does not
create a Gymnasium environment or global action mask.

Normal controllers receive sanitized `DecisionContext`, not native checkpoints
or unrestricted raw simulator state. Raw snapshots may be retained for audit
and future schema migration, but normal model input must cross the public
information boundary.

## Troubleshooting

- Import failures usually mean the selected Python version does not match the
  pybind build directory.
- PyTorch commands must use the Python 3.13 environment and matching
  `build-py313-final`.
- A restore mismatch is a hard gate failure. Do not weaken snapshot comparison
  or invent missing legacy fields.
- stdout is reserved for protocol output. Use `--log-file -` or stderr for
  diagnostic reports.

See [`current_status.md`](current_status.md) for current blockers and
[`experiment_log.md`](experiment_log.md) for verified results.
