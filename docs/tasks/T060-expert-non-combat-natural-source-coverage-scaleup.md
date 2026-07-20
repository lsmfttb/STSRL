# T060: Expert Non-Combat Natural Source Coverage Scale-Up

## Historical Objective

The original task proposed 10,000 fresh A20 terminal runs using
`expert_non_combat_v1` and the 100-simulation `oracle_search_v1` battle profile,
then applying the existing per-Act coverage gate.

## Disposition

Cancelled before implementation.

T040 already evaluated the same policy family at 1,000 terminal runs. That
experiment showed that the heuristic non-combat driver improved Act-1 Boss and
later-act reachability relative to the stochastic driver, but it did not provide
evidence that the unchanged battle/non-combat policy pair could naturally reach
Act 3, Act 4, or Heart states at a useful independent-source rate. Increasing the
number of runs by one order of magnitude would mainly estimate the occupancy
distribution induced by the same weak policy pair more precisely. It would not
identify whether the limiting factor is battle-search compute, battle-search
quality, non-combat planning, or an interaction between those components.

The planned scale-up also treated `expert_non_combat_v1` too strongly. That
controller is a human-designed bootstrap exploration policy used to improve
early source quality. It is not a teacher, a ground-truth policy, or an intended
imitation target for the final non-combat model.

## Superseding Task

T061, `A20 self-generated reachability bottleneck decomposition`, supersedes
this task. T061 uses matched interventions over battle-search budget and
non-combat behavior before authorizing any further natural-run scale-up.

## Preserved Boundaries

- Training remains simulator-only and does not use human trajectories, human
  action labels, or human expert imitation.
- Training-time Oracle information may be used only under an explicit
  information regime and may not be reported as normal-information performance.
- Battle and non-combat behavior retain separate controller provenance.
- Natural, Oracle-reached, assisted, transformed, constructed, and resampled
  distributions remain separately identified.
- The original T060 seed range and 10,000-run artifact plan were never executed
  and create no retained artifact dependency.

## Legacy Reference

Consult T040 for the accepted bootstrap-driver comparison, T050 for source-pool
sharding and merge support, T052 for later-act restored-battle evidence, and T059
for closure of the root-prior allocation-repair route.
