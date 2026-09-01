# T081: Scientific Artifact Eligibility Gate

Artifact Eligibility Required: true

## Artifact Eligibility Contract

- Inputs: the retained T043 checkpoint identities and provenance facts recorded
  by this task's historical audit; ignored raw checkpoints are optional
  inspection inputs and never required by CI.
- Reuse mode: `historical_reproduction` for exact historical dependency audits
  and `diagnostic_mechanism` for bounded checkpoint-conditional evidence.
- Claim boundary: preserve historical numerical results without treating either
  four-row smoke checkpoint as representative model-quality evidence.
- Required predicates: exact checkpoint identity and kind/schema integrity;
  known trainer provenance; diagnostic use requires at least one trainer row;
  new `scientific_quality_claim` use requires explicit scale/coverage facts and
  disallows an active smoke/debug override.
- Unavailable-fact behavior: retain an explicit unavailable fact and fail closed
  whenever that fact is required; never infer scale from filenames or paths.

## Objective

Prevent a reproducible but scientifically underqualified artifact from becoming a de facto canonical dependency merely because downstream tasks can verify its SHA, schema, and provenance.

T081 is a research control-plane repair prompted by the post-T080 audit of the T043 -> T044/T047/T048 -> T050/T051/T052 -> T062/T070 dependency chain. The failure mode is now explicit:

- artifact identity/integrity was checked rigorously;
- artifact scientific fitness for the downstream claim was not represented or enforced;
- the same T043 smoke/diagnostic checkpoint was therefore reused across increasingly consequential experiments;
- later negative evidence risked being interpreted as evidence about learned policy/value guidance in general rather than evidence conditional on that smoke checkpoint.

T081 adds a generic eligibility/claim-boundary contract before the next model-side scientific experiment. It does not retrain a model, change Search v2, alter the simulator, revive T079, or reinterpret historical executions as invalid.

## Historical Finding To Preserve

The implementation must encode, not rediscover or weaken, the following accepted control-plane finding recorded in research ledger #85:

1. T043 PR #41 implemented the assisted teacher/training workflow with smoke-scale evidence only. Its own report says training was allowed under a smoke override and full-scale A20 artifacts were intentionally left for later execution.
2. T044 later generated real T043-compatible checkpoints for evaluation, but the accepted checkpoint lineage remained smoke-scale. The retained `t043-assist_0-smoke` checkpoint has exactly four trainer rows. The later T042-`runs1000`-backed `t043-main-runs1000-assist_0-s4` lineage also selected only four sources / four trainer rows; `runs1000` describes the upstream source pool, not model-training scale.
3. No retained Git/PR provenance establishes that a broad or scale-qualified T043 checkpoint existed and was later lost. The auditable lineage instead shows that such a checkpoint was not produced there.
4. Historical downstream runs remain valid evidence for the exact artifact/controller tuple they executed. T081 must not rewrite their outcomes. The repair concerns eligibility of those artifacts for new/generalized claims.

## Core Distinction

T081 must make these two concepts separate and machine-readable:

### Artifact integrity

Questions such as:

- Is this the exact expected SHA-256?
- Does schema/version match?
- Is producer/source/trainer provenance exact?
- Is the artifact reproducible and unmodified?

### Artifact scientific eligibility

Questions such as:

- Was this artifact produced under a smoke/debug/training override?
- How many trainer and teacher rows actually produced the checkpoint?
- What source distributions/acts/rooms are represented?
- What training/readiness gate was passed, failed, overridden, or unknown?
- What claim scope did the producer explicitly authorize?
- Does the consuming task require stronger evidence than this artifact supplies?

Passing integrity must never imply passing scientific eligibility.

## Design Principle: Facts First, Requirements Per Consumer

T081 must not invent one global numeric rule such as "N rows means scale-qualified". Different experiments require different evidence.

Instead:

1. the artifact qualification surface records objective facts and producer-declared scope;
2. every consuming scientific task declares its required eligibility predicates before execution;
3. a preflight evaluates those requirements against the artifact facts and fails closed on unmet or unknown required fields.

This prevents both permissive reuse and arbitrary universal thresholds.

## Required Reuse Modes

The contract must distinguish at least these reuse modes:

### `historical_reproduction`

Exact historical artifacts may be reused to reproduce or audit the historical result that originally consumed them. Smoke/diagnostic status does not invalidate reproduction, but the output must preserve the original claim boundary and must not silently create a new generalized model-quality claim.

### `diagnostic_mechanism`

A smoke/diagnostic artifact may be used for bounded plumbing, restore, semantic equivalence, inference-cost, telemetry, mapping, API, or explicitly checkpoint-conditional mechanism experiments. The consuming task must state that its conclusion is conditional on that artifact and may not generalize negative model-quality evidence.

### `scientific_quality_claim`

Any task that intends to draw a new conclusion about learned policy/value guidance quality, value learning quality, training effectiveness, representation quality, model architecture quality, or a comparable model-level scientific property must declare explicit eligibility predicates. By default, an artifact produced under an active smoke/debug override or with unknown required scale/coverage facts is ineligible unless the task's scientific question explicitly studies that limitation.

## Qualification Facts

Implement one generic versioned qualification structure/report that can represent, where applicable:

- artifact path/id/kind and SHA-256;
- producer task/workflow identity;
- checkpoint schema/model metadata when the artifact is a checkpoint;
- exact trainer-input identity and `trainer_record_count`;
- teacher artifact identity and `teacher_record_count` where recoverable;
- upstream source-pool identity and source record/run counts where recoverable;
- training/readiness gate result;
- override kind/status (`none`, `smoke`, `debug`, named narrow override, `unknown`);
- source distribution kinds and available act/room/assistance coverage summaries;
- behavior-action availability or other label-provenance facts when relevant and already present in retained provenance;
- producer-declared claim scope / known limitations where current artifacts already record them;
- unresolved qualification fields rather than imputed values.

Do not infer training scale from directory/file names. In particular, a path containing `runs1000` must not be treated as evidence that the checkpoint was trained on 1,000 rows or runs.

## Consumer Requirement Contract

Provide a generic, versioned requirement surface that lets a task precommit:

- reuse mode;
- required artifact kinds/identities;
- required known qualification fields;
- allowed/disallowed override states;
- minimum trainer/teacher/source counts when the task genuinely needs and precommits them;
- required distribution/act/room coverage predicates when relevant;
- any task-specific claim-boundary predicates;
- whether an unavailable fact is fatal or may remain explicitly unresolved.

The evaluation result must be deterministic and machine-readable, with:

- `eligible: true/false`;
- every checked predicate;
- observed value;
- required value/rule;
- failure/unresolved reason;
- reuse mode and claim boundary.

No post-hoc weakening of requirements after outcomes are inspected.

## Historical T043 Regression Cases

T081 must add real-provenance regression coverage for both retained T043 lineages when the artifacts are locally available, and committed/synthetic qualification fixtures when raw ignored files are unavailable in CI:

1. `t043-assist_0-smoke` / checkpoint SHA-256 `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`:
   - exact trainer record count: 4;
   - smoke override / diagnostic-only provenance;
   - must be eligible for `historical_reproduction` and appropriately bounded diagnostic use;
   - must not pass a new `scientific_quality_claim` requirement that disallows smoke override.
2. `t043-main-runs1000-assist_0-s4` / checkpoint SHA-256 `ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3`:
   - upstream source pool may contain 1,000 terminal runs / thousands of starts;
   - trainer remains four rows;
   - qualification must use trainer provenance rather than `runs1000` naming;
   - must not be auto-upgraded to scale-qualified model evidence.

The test suite must include a deliberately misleading filename/path whose name implies large scale while its trainer provenance is smoke-scale, and prove that eligibility follows provenance facts rather than naming.

## Historical Claim-Boundary Audit

Produce a small committed or retained machine-readable audit of the T043 -> T070 model dependency chain sufficient to make these boundaries durable:

- which exact checkpoint each major downstream family consumed;
- its qualification facts available from retained provenance;
- whether the historical task used it for reproduction/mechanism/model-quality evidence;
- the maximum claim that remains justified without new model training.

At minimum cover T044, T047/T048, T050/T051/T052, T062, and T070.

The audit must not erase accepted numerical results. It annotates their dependency fitness and prevents later Planner synthesis from silently treating a smoke-conditioned negative as a general negative.

## Workflow Guard

Update the collaboration/task-spec control plane so that any newly published scientific task consuming learned checkpoints, teacher datasets, trainer datasets, or generated learning-source artifacts must include an **Artifact Eligibility Contract** section.

That section must name:

- input artifact(s);
- intended reuse mode;
- proposed scientific claim boundary;
- required qualification predicates;
- what happens if a required fact is unavailable.

Add a lightweight task-doc/test guard where practical so omission is review-visible or machine-detected. Do not require this section for tasks with no learned/data artifact dependency.

## Current Research Consequence

Until T081 is accepted, do not publish a new feature/encoding, value-target repair, architecture, or learned-guidance quality experiment that relies on a historical checkpoint as representative model evidence.

T080 remains `VALUE_TARGET_SEMANTICS_UNRESOLVED`. T081 does not change that result. It adds the newly discovered confounder that the exact T043 checkpoint used by T070 is a four-record smoke artifact.

After T081, Planner must reassess the next model-side task using qualification-aware evidence. It may decide that a minimally adequate self-generated training baseline is required before feature/value/architecture comparisons are scientifically meaningful.

## Out Of Scope

- model training or fine-tuning;
- teacher/search data collection;
- simulator or `sts_lightspeed` changes;
- Search v2 semantic changes;
- transposition/state identity work;
- changing the 4737/92 feature contract;
- choosing embeddings, Transformer/GNN/set encoders, or other architectures;
- value-target repair;
- T034 hidden-future sampling;
- T063/T066 promotion;
- rewriting or invalidating historical numerical experiment outputs.

## Acceptance Criteria

1. Integrity and scientific eligibility are represented as separate concepts and cannot be conflated by API/report success.
2. Qualification facts come from retained metadata/provenance or are marked unavailable; filenames never substitute for scale facts.
3. Consumer requirements are explicit, deterministic, precommitted, and fail closed on unmet required predicates.
4. `historical_reproduction`, `diagnostic_mechanism`, and `scientific_quality_claim` have distinct enforced claim boundaries.
5. The T043 `a231...` four-row smoke checkpoint cannot pass a new quality-claim requirement that rejects smoke override.
6. The T043 `ab684...` `runs1000`-named checkpoint cannot be mistaken for 1,000-row training; its four-row trainer provenance controls qualification.
7. Historical T044/T047/T048/T050/T051/T052/T062/T070 results remain numerically unchanged and are annotated, not rewritten.
8. New scientific task specifications consuming learning artifacts must declare an Artifact Eligibility Contract.
9. No model, Search, simulator, feature, training, or controller behavior changes occur.
10. Research ledger #85 is updated after acceptance with the final guard contract and any revised evidence priorities.

## Verification

Run standard repository gates plus focused tests for:

- qualification fact parsing;
- missing/unknown fail-closed behavior;
- reuse-mode boundaries;
- task-specific eligibility predicates;
- misleading filename vs provenance regression;
- exact T043 four-row regression fixtures;
- deterministic qualification/decision report generation;
- task-document guard behavior;
- `git diff --check`.

No WSL simulator run is required. If locally retained binary checkpoints are inspected for qualification facts, the implementation must also provide committed/synthetic fixtures so CI does not depend on ignored local artifacts.

## Planner Research Boundary

T081 addresses a research-validity dependency failure, not a new model hypothesis. It is complete when future tasks can no longer treat "exactly reproducible" as equivalent to "scientifically representative for this claim".
