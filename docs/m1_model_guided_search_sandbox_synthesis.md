# M1 Model-Guided Search Sandbox Synthesis

Last reviewed: 2026-06-26.

This document closes the M1 model-guided Oracle search sandbox at the planning
level. It summarizes the merged T025--T029 evidence and recommends the next
task batch without treating smoke-scale Oracle-like diagnostics as
normal-information, live-game, broad-training, or promoted controller-strength
evidence.

## Evidence Sources

The synthesis uses only merged repository status and accepted task evidence
recorded on `main` as of 2026-06-26:

- T025 added `search-decision-telemetry-v1` and
  `search-telemetry-summary-v1`. The accepted WSL smoke on a four-battle A20
  cohort reported 67 highest-mean Oracle decisions, 335 requested native
  simulations/root visits, 3,307 native simulator steps, zero model calls, and
  zero root-mapping failures. The most-visits diagnostic reported 60
  decisions, 300 requested simulations/root visits, 2,984 native simulator
  steps, zero model calls, and zero root-mapping failures.
- T026 added `search-guidance-inference-v1` for checkpoint scoring. Its
  accepted evidence was offline/local because the reviewed WSL Python
  environment did not have PyTorch installed.
- T027 added `teacher-guidance-calibration-report-v1`. Its accepted local gate
  passed, but no compatible external T024 `.pt` smoke checkpoint was found for
  an artifact-level calibration smoke.
- T028 added `model_guided_oracle_search_v1`. The accepted WSL evidence used
  ignored artifacts under `artifacts/t028-wsl-smoke/` and exercised eight A20
  restored battles with 123 model-guided Oracle decisions, 123 checkpoint model
  calls, three requested native playouts per decision, zero root-mapping
  failures, zero truncations, and zero errors. A maintainer audit also rebuilt
  a Python 3.13 shim from the pinned integration commit
  `242344c57c17c784708a6f072c905febc3f96527` and reran the controller path
  over four restored battles with 61 decisions and 61 model calls.
- T029 added `model-guided-search-fixed-comparison-v1`. The accepted WSL smoke
  used explicitly reported ignored artifacts under
  `artifacts/t029-wsl-smoke/`, evaluated eight restored A20 battles, and
  reported both baseline Oracle search and model-guided Oracle-like search at
  five wins and three losses. The configured native playout budget was equal at
  five per decision; observed native simulator steps were 5,178 for each
  controller; checkpoint model calls were zero for baseline and 120 for
  model-guided; restore failures, truncations, and evaluation errors were all
  zero.
- T024's accepted bridge evidence remains relevant input provenance for the
  M1 checkpoint path. Its WSL bridge over the accepted T023 smoke artifacts at
  budget 100 emitted 32 trainer-input v6 rows and wrote trainer artifact
  SHA-256
  `cca1960ecf1684470245f9bafc2afde3a0d5a77f5901981fef556d1ebf15797c`.

T030 does not add code, checkpoints, datasets, or simulator artifacts.

## Synthesis

M1 succeeded as search-engineering plumbing. The project now has a shared
telemetry schema, an offline checkpoint inference contract, calibration
diagnostics against Oracle teacher targets, a first versioned model-guided
Oracle-like controller, and an equal-source/equal-budget fixed-cohort
comparison report.

M1 did not demonstrate controller improvement. The accepted T029 smoke
comparison tied the baseline Oracle search result at the same native playout
budget while adding 120 checkpoint model calls for the model-guided controller.
That is useful integration evidence, not evidence for promotion.

The current model-guided controller can affect root selection only after the
native hidden-state search has already run. Current native APIs do not accept
public model priors for allocation, leaf values, uncertainty, or tree reuse.
Deeper search guidance therefore needs either a new native search surface or a
separate task that explicitly stays inside the current root-combination limit.

The current A20 data evidence remains too narrow for broad model conclusions.
The accepted T021/T023/T024 smoke chains were mainly Act 1, and the T009
broad-training gate remained closed. Broader natural coverage, sampled
optimization-weight coverage, constructed supplements, and teacher/checkpoint
refreshes must stay separately identified.

All current native search, teacher, and model-guided search evidence remains
`full_simulator_state_oracle_like` because the search copies hidden simulator
state. Public checkpoint features do not change that regime. No M1 result is
normal-information, live-game, broad-training, or controller-strength evidence.

## Decision

The next implementation priority should be a broader A20 coverage refresh and
data-gap report before deeper model-guided search work. The fixed comparison
did not show a search-strength gain, and the available checkpoint evidence is
still smoke-scale. A coverage refresh can determine whether the next useful
branch is broader teacher/checkpoint generation, later-act data collection,
or a narrower search-engineering experiment.

Normal-information belief search should remain behind two prerequisites:
better public-context/history encoder work and an authoritative
public-consistent hidden-future sampling boundary in the simulator. Directly
cloning Oracle actions or reporting hidden-state search as normal play remains
out of bounds.

## Proposed Next Batch

T031 is the immediate post-M1 candidate once T030 merges and the maintainer
updates lifecycle state. It refreshes A20 coverage using current commands and
publishes a data-gap report without training or promotion claims.

T032 depends on T031. It refreshes teacher, trainer-input, checkpoint, and
calibration evidence only after the refreshed source coverage contract is
available.

T033 is a draft public-context encoder task. It should define the structured
history, visible map, route, and visible-Boss encoding boundary before those
features become model inputs.

T034 is blocked on T033 and native simulator support. It defines the
public-consistent hidden-future sampling boundary required for normal belief
search.

T035 depends on refreshed data/checkpoint evidence. It is the next deeper
model-guided Oracle-like search task, but it must either use a new explicit
native guidance API or clearly preserve the current root-combination limit.
