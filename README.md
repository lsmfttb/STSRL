# sts-combat-rl

Battle-agent research infrastructure for Slay the Spire.

The project uses the external `sts_lightspeed` simulator as the authoritative
game implementation. The final objective is A20 Heart victory. The current
trainable scope is battle decisions; non-combat decisions remain under a
separate seeded driver.

## Read First

- [`docs/current_status.md`](docs/current_status.md): capabilities actually
  present on the latest `main`.
- [`docs/tasks/README.md`](docs/tasks/README.md): published implementation
  tasks, dependencies, and readiness.
- [`docs/collaboration_workflow.md`](docs/collaboration_workflow.md): branch,
  pull-request, review, and merge process.
- [`docs/project_architecture.md`](docs/project_architecture.md): authoritative
  target architecture and repository invariants.
- [`docs/README.md`](docs/README.md): complete documentation map.

## Current Main

`main` contains the current battle-agent research foundation through the
assisted source-generation and de-assisted evaluation batch. The high-level
shape is:

```text
external sts_lightspeed simulator
        |
        v
framework-neutral simulator adapter + CommunicationMod adapter
        |
        v
online battle controllers + separately versioned non-combat drivers
        |
        v
controlled runs, source pools, fixed cohorts, and restored evaluation
        |
        v
teacher data, trainer/model-input contracts, checkpoints, and search reports
```

The implemented surface includes checkpoint pools, Oracle-like native search
and teacher plumbing, optional PyTorch search-guidance training/inference,
public-context artifact propagation, assisted source-pool workflows, and
diagnostic fixed-cohort comparisons. The current gaps are still important:
`main` does not contain broad A20 neural training, promoted model-guided search
improvement, normal-information belief search, or interactive live-game A20
performance validation. See [`docs/current_status.md`](docs/current_status.md)
for the full implemented-capability list and [`docs/tasks/README.md`](docs/tasks/README.md)
for the authoritative task queue.

## Boundaries

- `sts_lightspeed` owns game rules and authoritative state transitions.
- Real simulator gates run through WSL, not Windows Python.
- Do not add local game mechanics, game files, simulator binaries, save files,
  Gymnasium, or Stable-Baselines3.
- Normal-information agents must not receive hidden RNG, unrevealed future
  encounters, hidden draw order, or the hidden Act-3 second Boss.
- A0 may be used for debugging or curriculum, but A20 is the final target and
  remains separately reported.
- stdout is reserved for protocol commands.

See [`AGENTS.md`](AGENTS.md) for concise repository-wide implementation rules.

## Install

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
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

Task-specific WSL simulator gates and artifact checks are listed in the
relevant task document.

## WSL Simulator

The external checkout is expected at:

```text
~/stsrl-spikes/sts_lightspeed
```

Run the current basic simulator smoke from Windows:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
```

See [`docs/sts_lightspeed_wsl_spike.md`](docs/sts_lightspeed_wsl_spike.md) for
commands available on `main`. Commands planned by future tasks belong in their
task documents until merged.

## Collaboration

`main` is the only integration line. Each published task uses one fresh branch
and one pull request based on the latest `main`. The main maintainer owns
project documentation, task publication, review, and merging; task implementers
own only their published task branch.

The large legacy commit `d56e10e` is a read-only recovery reference. It is not
an integration line and will not be merged wholesale. Its useful work is mapped
to focused tasks in [`docs/tasks/README.md`](docs/tasks/README.md).

Generated artifacts belong under the ignored `artifacts/` directory. Do not
commit large datasets or model checkpoints.
