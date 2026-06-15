# Historical Documents

Files in this directory preserve investigation notes, superseded plans, and
experiment records. They are useful for understanding why decisions were made,
but they are not current project contracts.

Use the current documentation in this order:

1. [`../../README.md`](../../README.md) for the project entry point.
2. [`../current_status.md`](../current_status.md) for implemented capabilities,
   known gaps, and immediate work.
3. [`../project_architecture.md`](../project_architecture.md) for repository-wide
   design rules.
4. [`../battle_dataset_search_and_sl_plan.md`](../battle_dataset_search_and_sl_plan.md)
   and
   [`../normal_information_search_and_resource_value_plan.md`](../normal_information_search_and_resource_value_plan.md)
   for active roadmaps.

Historical files must not be used to override those documents. Commands and
artifact versions in old notes may no longer be current.

## Contents

- `first_battle_trainer_plan.md`: the initial trainer and linear/PyTorch spike
  plan, retained for the evolution of the training pipeline.
- `simulator_candidate_scan.md` and `simulator_options.md`: the simulator
  selection process that led to `sts_lightspeed`.
- `conquer_the_spire_wsl_spike.md` and
  `decapitate_the_spire_wsl_spike.md`: rejected or secondary simulator build
  investigations.

Curated, still-relevant experiment results are summarized in
[`../experiment_log.md`](../experiment_log.md).
