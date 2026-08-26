# T065 Normative `non_combat_model_input_v1` Contract

This file is a **normative part of the T065 specification bundle**. It freezes the
complete deployable public model input used by target-table packing, both frozen
model seeds, held-out scoring, and Stage 6 online learned control.

The schema ID is exactly `non-combat-model-input-v1` and the schema version is
exactly `1`. Any change to the feature inventory, feature order, dimensions,
identity handling, numeric transform, normalizer construction, legal-action
representation, or state/action join after specification approval is a material
specification change and requires Maintainer re-approval.

This contract does not authorize implementation. T065 remains `DRAFT` until the
Main Maintainer approves the exact proposal head.

## Reused Current-Main Contracts

T065 does not invent a parallel feature system. The schema is a fixed composition
of already merged public contracts at planner baseline
`f9f3a835b3f94f41cbd22b48587cc8e65bd23644`:

- tactical schema ID `public-tactical-v2`, schema version `2`;
- tactical identity vocabulary version `public-identity-v1`;
- `DecisionContext.snapshot_features` produced by
  `encode_lightspeed_battle_snapshot`;
- `DecisionContext.legal_action_features` produced by
  `encode_simulator_actions`;
- public-context schema ID `public-context-model-input-v1`, schema version `1`;
- public-context feature names and order exactly
  `PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES`;
- public-context feature size exactly `103`.

The T065 encoder may call narrow reusable wrappers around those functions, but it
must not reinterpret or regenerate their fields independently.

## Frozen Dimensions And Top-Level Order

For one non-combat decision state:

- tactical snapshot vector dimension: exactly `4634`;
- public-context vector dimension: exactly `103`;
- T065 state vector dimension: exactly `4737`;
- one public legal-action vector dimension: exactly `92`.

The unnormalized T065 state vector is exactly:

```text
state_features = [
    DecisionContext.snapshot_features[0:4634],
    public_context_model_input_v1[0:103],
]
```

There is **no extra T065 screen one-hot, embedding, learned identity table,
feature cross, action-count feature, expert prior, behavior-action feature, or
hand-authored strategic feature**.

The four mandatory family indicators are the already frozen T033 public-context
screen positions:

- `MAP_SCREEN` -> `run_position.screen.map`;
- `REST_ROOM` -> `run_position.screen.rest`;
- `REWARDS` -> `run_position.screen.rewards`;
- `TREASURE_ROOM` -> `run_position.screen.treasure`.

For a replay-valid mandatory state, the corresponding T033 screen position must
be `1.0` and `run_position.screen.other` must be `0.0`. If the current public
projection cannot represent the mandatory screen this way, that state is not
silently re-encoded by T065; the already frozen failure/Case-D semantics apply.

## Frozen `public-tactical-v2` Snapshot Inventory

`DecisionContext.snapshot_features` is the exact `4634`-float compatibility
vector from `encode_lightspeed_battle_snapshot`. Its component order is frozen as
follows.

### Prefix scalars — 39 values

First, exactly these seven values:

1. `battle_active`
2. `act`
3. `floor_num`
4. `current_hp`
5. `max_hp`
6. `gold`
7. `ascension`

Then exactly these 17 player scalars, in order:

1. `current_hp`
2. `max_hp`
3. `energy`
4. `energy_per_turn`
5. `block`
6. `strength`
7. `dexterity`
8. `artifact`
9. `focus`
10. `vulnerable`
11. `weak`
12. `frail`
13. `cards_played_this_turn`
14. `attacks_played_this_turn`
15. `skills_played_this_turn`
16. `cards_discarded_this_turn`
17. `times_damaged_this_combat`

Then exactly these 15 summary values, in order:

1. `turn`
2. `hand_count`
3. `draw_count`
4. `discard_count`
5. `exhaust_count`
6. `monster_count`
7. `monsters_alive`
8. `potion_count`
9. `potion_capacity`
10. `player_power_count`
11. `relic_count`
12. `hand_available`
13. `discard_cards_available`
14. `exhaust_cards_available`
15. `relics_available`

### Card slots — 138 × 30 values

Slot order is exactly:

1. hand slots `0..9`;
2. discard slots `0..63`;
3. exhaust slots `0..63`.

Each slot is exactly this 30-value subvector:

1. `present`
2. `identity_code`
3. `identity_status_code`
4. `pile_is_hand`
5. `type.ATTACK`
6. `type.SKILL`
7. `type.POWER`
8. `type.CURSE`
9. `type.STATUS`
10. `rarity.BASIC`
11. `rarity.COMMON`
12. `rarity.UNCOMMON`
13. `rarity.RARE`
14. `rarity.SPECIAL`
15. `rarity.CURSE`
16. `cost`
17. `cost_for_turn`
18. `damage`
19. `block`
20. `magic_number`
21. `upgrade_count`
22. `misc`
23. `playable`
24. `requires_target`
25. `upgraded`
26. `exhausts`
27. `ethereal`
28. `retain`
29. `innate`
30. `exhaust_on_use_once`

### Monster slots — 5 × 22 values

Monster slots are `0..4`. Each slot is exactly:

1. `present`
2. `identity_code`
3. `identity_status_code`
4. `intent.ATTACK`
5. `intent.NON_ATTACK`
6. `intent.UNKNOWN`
7. `intent_identity_code`
8. `intent_identity_status_code`
9. `current_move_identity_code`
10. `current_move_identity_status_code`
11. `move_id`
12. `last_move_id`
13. `second_last_move_id`
14. `current_hp`
15. `max_hp`
16. `block`
17. `move_base_damage`
18. `move_hits`
19. `alive`
20. `targetable`
21. `half_dead`
22. `attacking`

### Potion slots — 5 × 5 values

Potion slots are `0..4`. Each slot is exactly:

1. `present`
2. `identity_code`
3. `identity_status_code`
4. `is_empty_slot`
5. `requires_target`

### Relic slots — 64 × 5 values

Relic slots are `0..63`. Each slot is exactly:

1. `present`
2. `identity_code`
3. `identity_status_code`
4. `counter`
5. `counter_available`

The dimension identity is therefore exactly:

`39 + 138*30 + 5*22 + 5*5 + 64*5 = 4634`.

T065 must assert this size during Stage 0 and when loading a checkpoint. A size
mismatch is a schema mismatch, not permission to infer a replacement layout.

## Frozen T033 Public-Context Inventory

The final 103 state values are exactly `PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES`
in this order:

```text
status.available
schema.current
projection.available
run_position.ascension.available
run_position.ascension
run_position.act.available
run_position.act
run_position.floor.available
run_position.floor
run_position.screen.battle
run_position.screen.rewards
run_position.screen.event
run_position.screen.shop
run_position.screen.rest
run_position.screen.treasure
run_position.screen.boss_reward
run_position.screen.map
run_position.screen.other
run_position.room_type.monster
run_position.room_type.elite
run_position.room_type.boss
run_position.room_type.event
run_position.room_type.shop
run_position.room_type.rest
run_position.room_type.treasure
run_position.room_type.rewards
run_position.room_type.other
run_position.is_battle
run_position.is_boss
run_position.is_elite
run_position.is_monster
run_position.visible_act_boss.available
run_position.visible_act_boss.act1
run_position.visible_act_boss.act2
run_position.visible_act_boss.act3
run_position.visible_act_boss.other
public_resources.current_hp.available
public_resources.current_hp
public_resources.max_hp.available
public_resources.max_hp
public_resources.hp_ratio.available
public_resources.hp_ratio
public_resources.gold.available
public_resources.gold
public_resources.potion_slot_count.available
public_resources.potion_slot_count
public_resources.occupied_potion_count.available
public_resources.occupied_potion_count
public_resources.deck_size.available
public_resources.deck_size
public_resources.relic_count.available
public_resources.relic_count
public_resources.curse_count.available
public_resources.curse_count
public_resources.blue_key.available
public_resources.blue_key
public_resources.green_key.available
public_resources.green_key
public_resources.red_key.available
public_resources.red_key
route_context.current_node.available
route_context.legal_routes.available
route_context.legal_route_count
route_context.next_room.monster_count
route_context.next_room.elite_count
route_context.next_room.boss_count
route_context.next_room.event_count
route_context.next_room.shop_count
route_context.next_room.rest_count
route_context.next_room.treasure_count
route_context.next_room.unknown_count
history_counts.entry_count
history_counts.monster
history_counts.elite
history_counts.boss
history_counts.event
history_counts.shop
history_counts.rest
history_counts.treasure
history_counts.reward
history_counts.card_choice
history_counts.relic_choice
history_counts.potion_choice
history_counts.key_choice
recent_public_outcomes.entry_count
recent_public_outcomes.battle_victory_count
recent_public_outcomes.battle_loss_count
recent_public_outcomes.current_hp_delta_total
recent_public_outcomes.max_hp_delta_total
recent_public_outcomes.gold_delta_total
recent_public_outcomes.potion_delta_total
identity_summary_v1.deck_identity_count
identity_summary_v1.attack_card_count
identity_summary_v1.skill_card_count
identity_summary_v1.power_card_count
identity_summary_v1.curse_card_count
identity_summary_v1.relic_identity_count
identity_summary_v1.potion_identity_count
identity_summary_v1.candidate_card_action_count
identity_summary_v1.candidate_potion_action_count
identity_summary_v1.candidate_end_turn_action_count
missingness.explicit_missing_field_count
missingness.problem_count
```

No T065-specific field may be inserted between, before, or after those values.

## Frozen Public Legal-Action Representation

For candidate legal action index `i`, `action_features` is exactly
`DecisionContext.legal_action_features[i]`, i.e. the 92-float
`public-tactical-v2` compatibility vector from `encode_simulator_actions`.

The 92 values are exactly:

1. scope one-hot in order `battle`, `game` — 2 values;
2. action-kind one-hot in this exact order — 31 values:
   `card`, `end_turn`, `potion`, `potion_discard`, `single_card_select`,
   `multi_card_select`, `event`, `reward_card`, `reward_gold`, `reward_key`,
   `reward_potion`, `reward_relic`, `card_remove`, `skip`, `boss_relic`,
   `card_select`, `map`, `treasure_open`, `treasure_leave`, `rest`,
   `shop_reward_card`, `shop_reward_gold`, `shop_reward_key`,
   `shop_reward_potion`, `shop_reward_relic`, `shop_card_remove`, `shop_skip`,
   `game_potion_use`, `game_potion_discard`, `game_unknown`, `battle_unknown`;
3. public action `identity_code`, then `identity_status_code` — 2 values;
4. `card_index`, then `target_index` — 2 values;
5. selected-card 30-value subvector in the card order frozen above;
6. selected-target 22-value subvector in the monster order frozen above;
7. `idx1`, `idx2`, `idx3` — 3 values.

Thus `2 + 31 + 2 + 2 + 30 + 22 + 3 = 92`.

The simulator legal-action order is preserved. `eligible_action_indices` is a
mask only; it is not a numeric model feature. T065 creates/scans one candidate
row for every eligible index, in increasing legal-action index order. No action
index, expert score, behavior probability, source behavior action, target value,
or terminal outcome is appended to the action vector.

## Frozen Missing And Unknown Semantics

T065 inherits the existing public encoders exactly:

- numeric/boolean values missing from the tactical compatibility view encode as
  `0.0` through the existing `_number` path;
- an absent fixed-capacity card/monster/potion/relic slot is the existing all-zero
  slot vector;
- public identity status codes are exactly `missing=0.0`, `known=1.0`,
  `unknown=2.0`;
- non-empty public identity strings use the existing 32-bit FNV-1a-style
  `_identity_code` converted to float; T065 does not replace it with a learned
  embedding or a new hash bucket;
- unknown categorical values use the existing public encoder behavior; T065 does
  not create a new OOV category;
- the T033 public-context encoder uses its existing availability flags and zero
  value for unavailable numeric fields, existing `other` categorical positions,
  and existing missingness counters;
- assistance-only or sanitizer-invalid public context remains an encoder problem
  and follows the already frozen supported-screen/Case-D semantics rather than
  being repaired inside the model input.

## Frozen Numeric Normalization

The raw vectors above are standardized using the same population-statistic
semantics already used by the merged PyTorch public policy/value model.

Build normalizers from **training split only** after the frozen 192 training
states (48 per mandatory family) and their complete eligible candidate-action
rows have passed target/schema completeness checks.

State normalizer:

- use exactly one raw 4737-float state row per selected training state, in frozen
  global selected-state order;
- convert the complete matrix to CPU `torch.float32`;
- `state_mean = states.mean(dim=0)`;
- `state_std = states.std(dim=0, unbiased=False).clamp_min(1.0)`.

Action normalizer:

- use every eligible 92-float candidate-action row from those same 192 training
  states, ordered first by frozen selected-state order and then increasing legal
  action index;
- convert the complete matrix to CPU `torch.float32`;
- `action_mean = actions.mean(dim=0)`;
- `action_std = actions.std(dim=0, unbiased=False).clamp_min(1.0)`.

Every model forward pass uses exactly:

```text
normalized_state  = (state_features  - state_mean)  / state_std
normalized_action = (action_features - action_mean) / action_std
```

The four normalizer tensors are part of each checkpoint and must be bitwise the
same for model seeds `653001` and `653002`; model seed does not change feature
normalization. Validation, held-out, and Stage 6 never recompute normalizers.
There is no other clipping, log transform, min/max scaling, reward scaling,
per-screen normalization, or online adaptation.

## Frozen Model Join Semantics

The ranker receives state and candidate action as **separate** normalized inputs.
There is no raw 4737+92 concatenation before the encoders.

The frozen network contract is:

```text
normalized_state[4737]
  -> state encoder -> state_embedding[64]

normalized_action[92]
  -> action encoder -> action_embedding[64]

joint = concat([state_embedding, action_embedding])  # exact order
joint[128]
  -> frozen joint head -> scalar q_floor
```

This file changes only the previously unspecified `d_state`, `d_action`, raw
feature composition, and normalization semantics. The layer counts, widths,
ReLU placements, scalar head, loss, optimizer, model seeds, minibatch RNG, and
training-step count remain those frozen in
`T065-frozen-execution-statistics-contract.md`.

## Same-Schema Requirement Across All Stages

The exact schema above is used in all of these places:

1. Stage 0 schema/size preflight;
2. Stage 2 selected-state/candidate target-table packing;
3. Stage 4 training for model seeds `653001` and `653002`;
4. validation checkpoint selection;
5. Stage 5 held-out scoring;
6. Stage 6 online `learned_non_combat_v1` scoring.

A checkpoint must record at minimum:

- `non_combat_model_input_schema_id = "non-combat-model-input-v1"`;
- `non_combat_model_input_schema_version = 1`;
- `tactical_feature_schema_id = "public-tactical-v2"`;
- `tactical_feature_schema_version = 2`;
- `identity_vocabulary_version = "public-identity-v1"`;
- `public_context_feature_schema_id = "public-context-model-input-v1"`;
- `public_context_feature_schema_version = 1`;
- `snapshot_feature_size = 4634`;
- `public_context_feature_size = 103`;
- `state_feature_size = 4737`;
- `action_feature_size = 92`;
- exact T033 public-context feature-name tuple;
- frozen `state_mean`, `state_std`, `action_mean`, `action_std`.

Loading or scoring with any mismatch fails closed. The Implementer may choose
ordinary module/class organization but may not change these scientific input
semantics without returning to specification review.
