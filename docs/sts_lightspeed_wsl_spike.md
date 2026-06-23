# sts_lightspeed WSL Operations

This guide lists simulator operations available on the latest `main`.
Checkpoint verification, portable battle-start pools, fixed structural
evaluation, Oracle-like native search teacher collection, Oracle fixed-cohort
comparison, structured battle resource outcome auditing with native terminal
resource identities, conservative constructed battle-start supplements, and
the pinned external source integration are current capabilities.

## Boundary

The authoritative simulator checkout stays outside this repository:

```text
~/stsrl-spikes/sts_lightspeed
```

This repository stores Python adapters, the source manifest, and legacy patches
kept as provenance. It does not vendor simulator source, simulator binaries,
game files, saves, or game mechanics.

Real simulator gates run through WSL, not Windows Python.

## Current Environment

```text
external checkout: ~/stsrl-spikes/sts_lightspeed
system build:      ~/stsrl-spikes/sts_lightspeed/build-py
repository in WSL: /mnt/d/DeadlycatCoding/STSRL
source manifest:   docs/sts_lightspeed_source_manifest.json
```

## Pinned Source Integration

The canonical day-to-day source integration is recorded in
[`sts_lightspeed_source_manifest.json`](sts_lightspeed_source_manifest.json):

```text
upstream:     https://github.com/gamerpuppy/sts_lightspeed.git
base commit:  7476a81954020087da31d41d16fddf475746ec2d
integration:  https://github.com/lsmfttb/sts_lightspeed.git
ref:          refs/heads/stsrl/t008-constructed-battle-start-v1
commit:       e9f0e7f104ea2bd908ba5b8f6528c240e6c92ad9
module:       slaythespire.StepSimulator
```

Verify the pinned source in a disposable worktree:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

The verifier reads the manifest, fetches the pinned ref, checks that it resolves
to the recorded commit, initializes `json` and `pybind11`, builds the Python
module in the disposable worktree, and asserts the native API capabilities
required by current `main`.

Rebuild the system `build-py` used by runtime gates only after the verifier
passes. This WSL bash command leaves tracked local changes in the external
checkout untouched, builds from a disposable worktree at the pinned integration
commit, backs up the previous `build-py`, and replaces only the build
directory:

```bash
source=/home/lsmft/stsrl-spikes/sts_lightspeed
worktree=$(mktemp -d /tmp/stsrl-rebuild-source.XXXXXX)
cleanup() {
  git -C "$source" worktree remove --force "$worktree" >/dev/null 2>&1 || true
  git -C "$source" worktree prune >/dev/null 2>&1 || true
}
trap cleanup EXIT
git -C "$source" fetch https://github.com/lsmfttb/sts_lightspeed.git refs/heads/stsrl/t008-constructed-battle-start-v1
git -C "$source" worktree add --detach "$worktree" e9f0e7f104ea2bd908ba5b8f6528c240e6c92ad9 >/dev/null
cd "$worktree"
git submodule update --init json pybind11
if [ -d "$source/build-py" ]; then
  mv "$source/build-py" "$source/build-py.pre-t008-$(date +%Y%m%d%H%M%S)"
fi
cmake -S "$worktree" -B "$source/build-py" -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build "$source/build-py" --target slaythespire -j 2
PYTHONPATH="$source/build-py" python3 -c "import slaythespire; sim=slaythespire.StepSimulator(slaythespire.CharacterClass.IRONCLAD, 1, 20); snap=sim.snapshot(); assert hasattr(sim, 'battle_search'); assert hasattr(sim, 'legal_battle_start_encounters'); assert hasattr(sim, 'rebuild_battle_start'); assert all(k in snap for k in ('potions', 'deck', 'relics', 'blue_key', 'green_key', 'red_key')); print(slaythespire.__file__)"
```

Current WSL-facing reports for the required runtime gates print the manifest
schema/version, upstream/base commit, integration ref/commit, Python module,
native capability inventory, legacy patch-stack disposition, and canonical
verifier command.

## Legacy Patch-Stack Provenance

The old ordered patches remain in the repository as reviewable provenance:

```text
patches/sts_lightspeed_step_simulator.patch
patches/sts_lightspeed_pybind11_v304.patch
patches/sts_lightspeed_checkpoint_restore.patch
patches/sts_lightspeed_battle_start_metadata.patch
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_non_combat_potion_actions.patch
patches/sts_lightspeed_gcc15_compat.patch
patches/sts_lightspeed_public_projection.patch
```

The old verifier, `scripts/verify_lightspeed_patch_stack.sh`, is retained only
for historical equivalence checks against external commit `7476a81`:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_patch_stack.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Future native-heavy tasks must extend the pinned source integration and update
the manifest rather than appending ad hoc patches to this retired stack unless
a later task explicitly reopens the patch-stack workflow.

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

Run this only after rebuilding `build-py` from the current verified pinned
source integration.
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

### Native Public-Projection Capability Audit

This T014 gate audits the raw native public projection, candidate-action parity,
checkpoint projection preservation, field availability, native source counts,
and explicit screen coverage gaps. It is a capability audit, not a sanitized
controller-context or real-game parity claim.

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-public-projection-capability-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

The accepted T018 A20 smoke observed 289 current decision screens, 1,209
resource snapshot comparisons, no resource mismatches, 289 candidate-action
parity passes, 289 checkpoint projection passes, no checkpoint failures, and
explicit coverage gaps for `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and
`TREASURE_ROOM`. Native persistent resources `deck`, `relics`,
`potion_identities`, and `keys` were available on all observed screens; the
sanitized public run context still treats those list/dict values as explicit
missing paths rather than normal controller inputs.

### Natural Battle-Start Pool And Fresh Restore

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && mkdir -p artifacts/checkpoints && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool artifacts/checkpoints/a20_seed1_3.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --battle-start-sample-count 20 --log-file - && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-restore artifacts/checkpoints/a20_seed1_3.jsonl --sim-seed 1 --sim-ascension 20 --log-file -"
```

The manifest excludes native checkpoint payloads. The restore command creates
fresh adapters and replays the recorded source seed and public action
identities; it must not be presented as cross-process native-checkpoint
serialization.

### Constructed Battle-Start Supplement Audit

This T008 gate first writes a portable natural A20 source pool, then audits
seeded constructed supplement proposals against that immutable pool. It reports
source counts, first/later-battle eligibility, per-transform audit rows,
constructed rows, distribution counts, native support, cap/Boss/ascension
violations, and source public-context status. Constructed rows supplement
natural data and remain separately tagged.

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && rm -f /tmp/t008_pool.jsonl /tmp/t008_constructed.jsonl && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/t008_pool.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 120 --log-file - && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-constructed-battle-start-audit --constructed-start-pool /tmp/t008_pool.jsonl --constructed-start-output /tmp/t008_constructed.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 120 --log-file -"
```

The accepted T008 A20 audit over seeds `1..3` reported 13 natural source
starts, 3 first-battle sources, 10 later-battle sources, 39 transform audit
rows, 11 constructed rows, resulting distributions `natural_run: 13` and
`constructed_supplement: 11`, no unsupported native operations, no
cap/Boss/ascension violations, and source public context available for every
audit row. Repeating the same audit over the same pool and policy seed produced
matching artifact SHA256 digests.

### Fixed Structural Battle Evaluation

After producing a portable pool with the current verified pinned source, freeze
and evaluate a deterministic structural cohort. This is a plumbing and
comparison gate, not a policy-strength benchmark:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && mkdir -p artifacts/evaluations && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-fixed-battle-evaluation artifacts/checkpoints/a20_seed1_3.jsonl --fixed-evaluation-cohort artifacts/evaluations/a20_seed1_3_cohort.jsonl --fixed-evaluation-report artifacts/evaluations/a20_seed1_3_report.jsonl --sim-ascension 20 --sim-steps 200 --log-file -"
```

The command restores every selected start in a fresh adapter, reports restore,
selection, controller, and simulator failures explicitly, and writes separate
natural-weighted, encounter-macro, room-type-macro, and per-stratum results.
Use a `build-py` rebuilt from the verified pinned source; an older system build
can lack completed-battle outcome fields even when the repository is current.

### Oracle Search Teacher Collection

This T006 workflow uses hidden simulator state and must be reported only as
`full_simulator_state_oracle_like` teacher/diagnostic data:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-oracle-search-teacher /tmp/t006-pool.jsonl --oracle-teacher-output /tmp/t006-teacher.jsonl --oracle-search-simulations 20 --sim-ascension 20 --sim-steps 200 --log-file -"
```

The pool must first be created with the current battle-start-pool workflow.
The teacher artifact preserves source checkpoint provenance, occurrence-safe
legal-action identities, root statistics, the direct teacher action, the soft
root-visit target, optional behavior action, public-context availability, and
Oracle controller provenance.

### Oracle Fixed-Cohort Evaluation

This T006 workflow loads an existing fixed cohort unchanged and evaluates
`highest_mean` plus the `most_visits` diagnostic on the same cohort:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-oracle-fixed-evaluation /tmp/t006-cohort.jsonl --oracle-search-simulations 20 --oracle-root-selection highest_mean --sim-ascension 20 --sim-steps 200 --log-file -"
```

Results from this command are Oracle-like diagnostic evidence only. They are
not normal-information or live-game performance.

### Structured Battle Resource Outcome Audit

This T012/T018 gate validates schema plumbing, artifact propagation, explicit
missingness, component-level reporting, and native terminal resource identity
coverage for battle-end resource outcomes. It fails if required T018
identity-bearing components are missing or unavailable.

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-resource-outcome-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

The accepted T018 A20 smoke over seeds `1..3` reported 13 natural starts, 13
completed battles, 10 `PLAYER_VICTORY`, 3 `PLAYER_LOSS`, 13 available
structured outcome records, no pool or structural audit problems, no
unsupported native fields, and no T018 identity gate problems. Terminal
`potion_slots`, `deck`, `curses`, `relics`, and `keys` were all available.

## Troubleshooting

- Import failures usually mean the selected Python version does not match the
  pybind build directory.
- stdout is reserved for protocol output. Use `--log-file -` for diagnostics.
- A command documented only in a future task is not expected to exist on
  `main`.

See [`current_status.md`](current_status.md) for current implementation truth
and [`experiment_log.md`](experiment_log.md) for historical evidence.
