# AGENTS.md

This file contains concise, repository-wide rules for coding agents. Read these
documents before making architectural changes:

1. `docs/current_status.md`
2. `docs/project_architecture.md`
3. the relevant active roadmap under `docs/`

Historical files under `docs/history/` explain past decisions but are not
current contracts.

## Scope And Simulator Boundary

- The trainable scope is currently battle decisions. Non-combat decisions stay
  under a separately named driver.
- Treat A20 Heart victory as the final target. A0 is only a separately reported
  debugging or curriculum distribution.
- `sts_lightspeed` is the authoritative game implementation. Do not implement
  Slay the Spire mechanics locally.
- Real `sts_lightspeed` gates run through WSL, not Windows Python.
- Do not add game files, jars, mods, save files, large binaries, Gymnasium, or
  Stable-Baselines3.
- PyTorch battle-policy/value work is allowed behind the optional `train`
  dependency group.

## Information And Objective

- Normal-information controllers, features, labels, and search trees must not
  receive hidden RNG state, unrevealed future encounters, hidden draw order, or
  the hidden Act-3 second Boss.
- Treat the current native `BattleScumSearcher2` as
  `full_simulator_state_oracle_like`, never as a normal-information baseline.
- Preserve complete player-visible run context as the long-term state target:
  full visible history including events and choices, complete visible map and
  routes, visible Act Boss, and persistent public resources.
- Missing context must be explicit. Do not guess missing history or provenance.
- Preserve battle outcome, terminal absolute current HP, and structured
  battle-end resources as separate labels. Do not normalize current HP by max
  HP or permanently scalarize resources with fixed reward weights.
- Search is the primary battle-policy direction. Evaluate learned models mainly
  as search guidance or acceleration; raw policy strength is diagnostic.

## Controllers And Execution

- Every online action selector implements the explicit controller contract and
  publishes complete provenance.
- Keep battle and non-combat controllers separate even when routed through one
  complete run.
- Use `execute_controlled_run` as the authoritative complete-run advancement
  path. Specialized replay, restore, fixed-battle, and labeling loops may exist
  only for their distinct boundary and must reuse shared selection semantics.
- Non-combat natural-run drivers remain seeded and stochastic. Apply priors by
  changing hierarchical category probabilities, not by creating one
  deterministic route.
- Keep low-probability legal non-combat branches reachable, including taking or
  skipping relics, opening or leaving treasure, using non-combat potions, and
  discarding potions.
- Versioned controller names are behavior contracts. Behavior changes require a
  new version; old versions remain explicitly constructible for diagnostics.

## Data And Evaluation

- Keep natural-run, stratified-training, constructed, paired-counterfactual,
  normal-information, Oracle, and SL-enabled distributions separately tagged
  and reported.
- Build structural strata from rule-defined metadata such as ascension, act,
  room type, and encounter id. Do not filter states using hand-written deck or
  relic quality judgments.
- Preserve the sampling component and source checkpoint on every sampled
  decision. Repeating a checkpoint changes training weight, not coverage.
- Report battle-start coverage separately from battle wins and later-act
  progression.
- Keep natural-weighted, encounter-macro, and room-type-macro evaluation
  results separate.
- Broad neural training must pass the explicit scale/distribution gate per
  ascension and act. Use the named under-covered override only for documented
  smoke or narrow curriculum experiments.
- Constructed battle starts are supplements, not natural data. Keep them
  stochastic, conservative, same-ascension, explicitly tagged, and separately
  evaluated. HP augmentation may use a practical bounded approximation;
  authoritative replay can be used for high-confidence audits but is not a
  mandatory path for every small HP change.
- Do not replace a visible Act Boss in ordinary training. Boss replacement is a
  separately tagged counterfactual because earlier decisions were conditioned
  on that Boss.
- Keep DAgger behavior actions distinct from search teacher actions.

## Code And Artifacts

- Follow `docs/project_architecture.md` as the top-level design contract.
- Keep CLI modules limited to parsing and routing. Put workflows in
  `src/sts_combat_rl/commands/` and reusable logic below that layer.
- Keep CommunicationMod formatting centralized in
  `src/sts_combat_rl/comm/protocol.py`.
- Reserve stdout for protocol commands; use stderr or log files for debugging.
- Writers emit only current artifact schemas. Readers migrate legacy artifacts
  sequentially before business logic runs; never guess missing provenance.
- Portable replay traces must disambiguate duplicate legal action ids.
- Keep legacy fixtures and migration regression tests. Do not scatter permanent
  legacy-version branches through current business logic.
- Keep dependencies minimal and avoid unrelated refactors.

## Parallel Development

- Use focused branches with an explicit ownership boundary.
- Do not revert or overwrite changes from other branches or agents.
- Before merging, review behavior, provenance, artifact compatibility, tests,
  and documentation impact.
- Keep current contracts and current status in their authoritative documents;
  put superseded plans and experiment narratives under `docs/history/`.

## Recommended Checks

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Real simulator gates:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-checkpoint-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --checkpoint-replay-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool-restore-smoke POOL.jsonl --sim-ascension 20 --pool-restore-limit 0 --log-file -"
```
