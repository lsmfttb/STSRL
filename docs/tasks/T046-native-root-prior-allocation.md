# T046: Native Root-Prior Allocation Search Surface

## Objective

Add a minimal `sts_lightspeed` native search surface that lets explicit root
action priors influence root playout allocation before final root selection,
then wire that surface into STSRL with validation, telemetry, and smoke
evidence.

This task tests the T045 recommendation that model guidance needs to enter
search earlier than post-search root blending. It is still Oracle-like
engineering work, not normal-information search and not controller promotion.

## Current Main Baseline

T045 completed the post-T044 failure analysis. The accepted smoke evidence
found model-guided search overrides at 0/446 decisions, tied model-guided
search with baseline search on all analyzed battles, and marked
`integration-too-late`, `distribution-mismatch`, and `model-too-weak` as active
signals. The recommended primary path was native root-prior allocation before
another training loop.

Current `model_guided_oracle_search_v2` still runs the native hidden-state
`battle_search` once and applies public checkpoint scores only after native
search has finished. The current pinned native API does not accept policy
priors, learned leaf values, model callbacks, or allocation hooks.

## Dependencies

- T045 is complete.
- T017 and T020 are complete and define the pinned `sts_lightspeed`
  integration-line workflow.

## Inputs And Artifacts

This task does not require T043/T044 retained smoke artifacts as inputs.

Required inputs are:

- the current pinned `sts_lightspeed` source manifest;
- small committed fixtures or WSL smoke-generated battle states sufficient to
  exercise legal root actions, duplicate action identity, potion inclusion when
  available, uniform priors, one-hot priors, and invalid-prior rejection.

The primary generated output is a small
`native-root-prior-allocation-report-v1` diagnostic report. Generated reports
remain under ignored `artifacts/` paths unless a compact fixture is needed for
tests.

Any fork-side source change must advance the pinned integration commit through
`docs/sts_lightspeed_source_manifest.json`. The PR must name the fork branch,
commit, rebuild command, verifier result, and generated report hash.

## Scope

- Add a minimal fork-side native API equivalent to:

  ```text
  battle_search_with_root_priors(
      snapshot,
      simulations,
      include_potions,
      root_action_priors,
      prior_temperature,
      min_visits_per_legal_action,
      prior_allocation_weight
  )
  ```

  The exact binding name may differ if the PR justifies compatibility, but the
  behavior contract above must be preserved.
- Allocate root playouts only at the root. First ensure each eligible legal
  root action receives the configured minimum visits when the budget allows;
  allocate remaining simulations by uniform priors, supplied priors, or a
  documented mixture.
- Return root rows compatible with current `battle_search` consumers,
  including occurrence-safe action identity, visit counts, mean values, native
  simulator steps, unmapped edge telemetry, and explicit allocation metadata.
- Update the source manifest capability inventory for the new native surface.
- Add STSRL adapter and command-layer plumbing for a root-prior allocation
  smoke/report workflow. CLI modules may parse and route; reusable validation,
  reporting, and simulator logic must live below the CLI layer.
- Validate prior keys against the current legal root action identities before
  calling native search. Unknown, duplicate, or malformed action identities
  fail closed.
- Preserve existing baseline `battle_search` behavior and existing model-guided
  controllers unless the task explicitly adds a separate diagnostic wrapper.

## Out Of Scope

- Learned leaf-value evaluation, Python model callbacks inside native search,
  uncertainty-aware tree policies, tree reuse, or belief-state search.
- New T043/T044 training, teacher collection, fixed-cohort comparison, or
  controller promotion.
- A T047-style equal-budget performance comparison between baseline search,
  post-search root blending, and root-prior allocation.
- Normal-information claims, live-game claims, broad-training claims, or A20
  performance claims.
- Reimplementing Slay the Spire mechanics, legal actions, or battle mutation in
  repository Python code.

## Design Constraints

- The new surface remains `full_simulator_state_oracle_like` because native
  search copies hidden simulator state.
- The simulator owns legal action enumeration, root expansion, potion legality,
  battle advancement, and terminal outcomes.
- Priors are advisory allocation inputs, not labels or hidden-state facts.
  Public model priors may be supplied later, but this task can validate the
  surface with explicit uniform and one-hot priors.
- Root action identity mapping must be occurrence-safe for duplicate cards,
  targets, potions, and end-turn actions.
- Mapping failures, unsearched legal actions, exhausted budgets, invalid
  priors, and missing native fields must be explicit report fields.
- Existing artifact readers must not guess missing provenance. Any new schema
  must be versioned and validated.
- Large or long-running WSL stages must follow the worker/shard reporting rule
  from `docs/tasks/README.md`; this task should only need smoke-scale WSL
  evidence.

## Deliverables

- Fork-side native root-prior allocation API and pybind surface.
- Updated `docs/sts_lightspeed_source_manifest.json` with the new pinned
  source commit and native capability entry.
- STSRL adapter/reporting code for `native-root-prior-allocation-report-v1`.
- A smoke command or workflow that runs baseline `battle_search`, uniform
  root-prior search, and one-hot root-prior search on the same restored or
  generated battle states.
- Focused tests for prior validation, occurrence-safe action mapping, uniform
  allocation metadata, one-hot allocation effect, invalid-prior failure,
  report schema validation, and no-promotion wording.
- Documentation impact notes in the PR report.

## Acceptance Criteria

- The canonical source verifier succeeds against the new pinned fork commit.
- Existing `battle_search` consumers and tests continue to pass without
  requiring priors.
- Uniform root priors with the same budget and legal-action set return
  compatible root rows, zero root mapping failures, explicit allocation
  metadata, and no missing eligible root actions except when the budget is too
  small to visit all legal actions.
- A one-hot prior with surplus budget gives the preferred eligible action
  strictly more allocated root visits than every non-preferred eligible action,
  unless the PR reports a native tie or budget constraint that makes the smoke
  state unsuitable.
- Unknown, duplicate, malformed, or illegal prior action identities fail closed
  before native search mutates simulator state.
- The report includes configured simulations, prior temperature,
  minimum-visits setting, prior allocation weight, visited root counts,
  unsearched legal-action counts, native simulator steps, model-call count,
  root mapping failures, source identity, and information regime.
- The PR makes no normal-information, live-game, broad-training,
  controller-promotion, or A20 performance claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T046 tests,
task-doc checks, and `git diff --check`.

Before WSL evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run a WSL native root-prior allocation smoke on explicitly reported seeds,
budgets, priors, and output paths. If the PR adds a named CLI command, the PR
must report the exact command. A representative shape is:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-native-root-prior-allocation-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --search-budget 20 --log-file -"
```

If any WSL stage exceeds smoke/debug scale, shard it and report worker count,
shard count, record or seed ranges, wall-clock cost, and any lower-worker
reason.

## Legacy Reference

Consult T006 for Oracle-like root rows, T017/T020 for source-manifest workflow,
T025 for search telemetry, T028/T035 for post-search model-guided root
selection, T041 for root-row mapping repair patterns, and T045 for the
failure taxonomy that selected this path. Do not port unrelated legacy search
or local mechanics code.

## PR Report

The PR must report task ID, fork branch and commit, source manifest before and
after, rebuild command, verifier output, native API shape, allocation algorithm
summary, smoke seeds and budgets, consumed/generated artifact paths and
SHA-256 hashes, uniform and one-hot allocation summaries, invalid-prior
failure evidence, local and WSL verification results, documentation impact,
known limitations, and whether any acceptance criterion remains unmet.
