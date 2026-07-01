#!/usr/bin/env bash
# Verify the pinned external sts_lightspeed source integration.

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 /path/to/sts_lightspeed-checkout [manifest.json]" >&2
    exit 2
fi

source_checkout=$(cd "$1" && pwd)
repo_root=$(cd "$(dirname "$0")/.." && pwd)
manifest_path="${2:-$repo_root/docs/sts_lightspeed_source_manifest.json}"

manifest_output=$(
    PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}" python3 - "$manifest_path" <<'PY'
from pathlib import Path
import sys

from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest

manifest = load_lightspeed_source_manifest(Path(sys.argv[1]))
values = [
    manifest.integration.repository_url,
    manifest.integration.ref,
    manifest.integration.commit,
    manifest.upstream.repository_url,
    manifest.upstream.base_commit,
    manifest.python_module.name,
    manifest.python_module.simulator_class,
    manifest.build.build_directory,
    manifest.build.cmake_target,
    manifest.build.cmake_policy_version_minimum,
    manifest.schema_id,
    str(manifest.manifest_version),
    manifest.native_projection_contract.schema_id,
    manifest.native_projection_contract.external_base_commit_label,
    manifest.native_projection_contract.patch_identity,
    *manifest.build.submodules,
]
for value in values:
    print(value)
PY
) || {
    echo "failed to read sts_lightspeed source manifest: $manifest_path" >&2
    exit 2
}

mapfile -t manifest_values <<<"$manifest_output"
if [[ ${#manifest_values[@]} -lt 15 ]]; then
    echo "source manifest parser returned incomplete verifier metadata" >&2
    exit 2
fi

integration_url="${manifest_values[0]}"
integration_ref="${manifest_values[1]}"
integration_commit="${manifest_values[2]}"
upstream_url="${manifest_values[3]}"
base_commit="${manifest_values[4]}"
module_name="${manifest_values[5]}"
simulator_class="${manifest_values[6]}"
build_dir="${manifest_values[7]}"
cmake_target="${manifest_values[8]}"
cmake_policy_version_minimum="${manifest_values[9]}"
manifest_schema_id="${manifest_values[10]}"
manifest_version="${manifest_values[11]}"
native_projection_schema_id="${manifest_values[12]}"
native_projection_base_label="${manifest_values[13]}"
native_projection_patch_identity="${manifest_values[14]}"
submodules=("${manifest_values[@]:15}")

if ! git -C "$source_checkout" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "not a git checkout: $source_checkout" >&2
    exit 2
fi

if ! git -C "$source_checkout" cat-file -e "$base_commit^{commit}" 2>/dev/null; then
    echo "source checkout is missing upstream base commit: $base_commit" >&2
    exit 1
fi

echo "sts_lightspeed source manifest: $manifest_schema_id v$manifest_version"
echo "upstream: $upstream_url @ $base_commit"
echo "integration: $integration_url $integration_ref @ $integration_commit"

if ! git -C "$source_checkout" fetch --no-tags "$integration_url" "$integration_ref"; then
    echo "failed to fetch pinned integration ref" >&2
    exit 1
fi

fetched_commit=$(git -C "$source_checkout" rev-parse FETCH_HEAD^{commit})
if [[ "$fetched_commit" != "$integration_commit" ]]; then
    echo "integration ref resolved to $fetched_commit, expected $integration_commit" >&2
    exit 1
fi

if ! git -C "$source_checkout" merge-base --is-ancestor "$base_commit" "$integration_commit"; then
    echo "integration commit is not based on manifest upstream base commit" >&2
    exit 1
fi

worktree=$(mktemp -d "${TMPDIR:-/tmp}/stsrl-lightspeed-source.XXXXXX")
cleanup() {
    git -C "$source_checkout" worktree remove --force "$worktree" >/dev/null 2>&1 || true
    git -C "$source_checkout" worktree prune >/dev/null 2>&1 || true
}
trap cleanup EXIT

git -C "$source_checkout" worktree add --detach "$worktree" "$integration_commit" >/dev/null

cd "$worktree"
for submodule in "${submodules[@]}"; do
    expected_submodule_commit=$(
        git -C "$worktree" ls-tree HEAD "$submodule" | awk '{print $3}'
    )
    if [[ -n "$expected_submodule_commit" ]] \
        && git -C "$source_checkout/$submodule" rev-parse --is-inside-work-tree \
            >/dev/null 2>&1 \
        && git -C "$source_checkout/$submodule" cat-file \
            -e "$expected_submodule_commit^{commit}" 2>/dev/null; then
        mkdir -p "$worktree/$submodule"
        git -C "$source_checkout/$submodule" archive "$expected_submodule_commit" \
            | tar -x -C "$worktree/$submodule"
        continue
    fi
    git submodule update --init "$submodule"
done
cmake -S . -B "$build_dir" -DCMAKE_POLICY_VERSION_MINIMUM="$cmake_policy_version_minimum"
cmake --build "$build_dir" --target "$cmake_target" -j "${STSRL_LIGHTSPEED_BUILD_JOBS:-2}"

PYTHONPATH="$worktree/$build_dir:$repo_root/src${PYTHONPATH:+:$PYTHONPATH}" python3 - \
    "$manifest_path" \
    "$module_name" \
    "$simulator_class" \
    "$native_projection_schema_id" \
    "$native_projection_base_label" \
    "$native_projection_patch_identity" <<'PY'
from importlib import import_module
from pathlib import Path
import sys

from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest


def fail(message: str) -> None:
    raise SystemExit(message)


manifest_path = Path(sys.argv[1])
module_name = sys.argv[2]
simulator_class_name = sys.argv[3]
projection_schema_id = sys.argv[4]
projection_base_label = sys.argv[5]
projection_patch_identity = sys.argv[6]
manifest = load_lightspeed_source_manifest(manifest_path)

module = import_module(module_name)
if not hasattr(module, "CharacterClass"):
    fail("module does not expose CharacterClass")
character_class = getattr(module.CharacterClass, "IRONCLAD", None)
if character_class is None:
    fail("CharacterClass.IRONCLAD is missing")
simulator_class = getattr(module, simulator_class_name, None)
if simulator_class is None:
    fail(f"{simulator_class_name} is missing")

sim = simulator_class(character_class, 1, 20)
for method_name in (
    "reset",
    "snapshot",
    "observation",
    "legal_actions",
    "step",
    "capture_checkpoint",
    "restore_checkpoint",
    "public_projection",
    "battle_search",
    "battle_search_with_root_priors",
    "legal_battle_start_encounters",
    "rebuild_battle_start",
):
    if not hasattr(sim, method_name):
        fail(f"StepSimulator.{method_name} is missing")

snapshot = sim.snapshot()
if not isinstance(snapshot, dict):
    fail("StepSimulator.snapshot() must return a dict")
for key in (
    "screen_state",
    "outcome",
    "act",
    "floor_num",
    "room_type",
    "ascension",
    "cur_hp",
    "max_hp",
    "gold",
    "potion_count",
    "potion_capacity",
    "potions",
    "deck",
    "relics",
    "blue_key",
    "green_key",
    "red_key",
):
    if key not in snapshot:
        fail(f"snapshot missing required field {key!r}")
for key in ("potions", "deck", "relics"):
    if not isinstance(snapshot.get(key), list):
        fail(f"snapshot {key!r} must be a list")
for key in ("blue_key", "green_key", "red_key"):
    if not isinstance(snapshot.get(key), bool):
        fail(f"snapshot {key!r} must be a bool")
if snapshot["deck"]:
    first_card = snapshot["deck"][0]
    if not isinstance(first_card, dict):
        fail("snapshot deck entries must be objects")
    for key in ("deck_index", "id", "id_label", "name", "type"):
        if key not in first_card:
            fail(f"snapshot deck entry missing required field {key!r}")
if snapshot["relics"]:
    first_relic = snapshot["relics"][0]
    if not isinstance(first_relic, dict):
        fail("snapshot relic entries must be objects")
    for key in ("relic_index", "id", "id_label", "name", "counter"):
        if key not in first_relic:
            fail(f"snapshot relic entry missing required field {key!r}")
if snapshot["potions"]:
    first_potion = snapshot["potions"][0]
    if not isinstance(first_potion, dict):
        fail("snapshot potion entries must be objects")
    for key in ("potion_index", "id", "id_label", "name"):
        if key not in first_potion:
            fail(f"snapshot potion entry missing required field {key!r}")

observation = sim.observation()
if not isinstance(observation, list) or not observation:
    fail("StepSimulator.observation() must return a non-empty list")

actions = sim.legal_actions()
if not isinstance(actions, list) or not actions:
    fail("StepSimulator.legal_actions() must return a non-empty list")
action = actions[0]
for attr in ("scope", "bits", "kind", "label", "idx1", "idx2", "idx3"):
    if not hasattr(action, attr):
        fail(f"native action missing attribute {attr}")

checkpoint = sim.capture_checkpoint()
transition_snapshot = sim.step(action)
if not isinstance(transition_snapshot, dict):
    fail("StepSimulator.step() must return a dict snapshot")
restored = sim.restore_checkpoint(checkpoint)
if not isinstance(restored, dict):
    fail("StepSimulator.restore_checkpoint() must return a dict snapshot")

projection = sim.public_projection()
if not isinstance(projection, dict):
    fail("StepSimulator.public_projection() must return a dict")
if projection.get("schema_id") != projection_schema_id:
    fail("native public projection schema id mismatch")
if projection.get("external_base_commit") != projection_base_label:
    fail("native public projection base commit label mismatch")
if projection.get("patch_identity") != projection_patch_identity:
    fail("native public projection patch identity mismatch")

required_projection_fields = (
    "screen_identity",
    "visible_act_boss",
    "visible_map_graph",
    "current_map_node",
    "immediately_legal_routes",
    "persistent_resources",
    "screen_payload",
    "candidate_actions",
)
for key in required_projection_fields:
    field = projection.get(key)
    if not isinstance(field, dict) or "availability" not in field:
        fail(f"public projection field {key!r} is malformed")

candidate_actions = projection["candidate_actions"]
if candidate_actions.get("availability") != "available":
    fail("public projection candidate_actions must be available")
if not isinstance(candidate_actions.get("value"), list):
    fail("public projection candidate_actions value must be a list")

persistent_resources = projection["persistent_resources"]
if persistent_resources.get("availability") != "available":
    fail("public projection persistent_resources must be available")
resource_values = persistent_resources.get("value")
if not isinstance(resource_values, dict):
    fail("public projection persistent_resources value must be an object")
for key in ("current_hp", "max_hp", "gold", "potion_count", "potion_capacity"):
    field = resource_values.get(key)
    if not isinstance(field, dict) or field.get("availability") != "available":
        fail(f"persistent resource {key!r} must be available")
for key in ("deck", "relics", "potion_identities", "keys"):
    field = resource_values.get(key)
    if not isinstance(field, dict) or field.get("availability") != "available":
        fail(f"persistent resource {key!r} must be available")
    value = field.get("value")
    if key == "keys":
        if not isinstance(value, dict):
            fail("persistent resource 'keys' value must be an object")
        for flag in ("blue_key", "green_key", "red_key"):
            if not isinstance(value.get(flag), bool):
                fail(f"persistent resource key flag {flag!r} must be a bool")
    elif not isinstance(value, list):
        fail(f"persistent resource {key!r} value must be a list")

battle_snapshot = sim.snapshot()
for _ in range(200):
    if battle_snapshot.get("screen_state") == "BATTLE" and battle_snapshot.get(
        "battle_active"
    ):
        break
    actions = sim.legal_actions()
    if not isinstance(actions, list) or not actions:
        fail("could not reach battle: legal_actions returned no actions")
    battle_snapshot = sim.step(actions[0])
    if not isinstance(battle_snapshot, dict):
        fail("StepSimulator.step() must return a dict while reaching battle")
else:
    fail("could not reach a battle to verify StepSimulator.battle_search")

encounter_candidates = sim.legal_battle_start_encounters()
if not isinstance(encounter_candidates, list) or not encounter_candidates:
    fail("StepSimulator.legal_battle_start_encounters() must return candidates")
first_candidate = encounter_candidates[0]
if not isinstance(first_candidate, dict):
    fail("battle-start encounter candidates must be objects")
for key in ("id", "encounter_id"):
    if key not in first_candidate:
        fail(f"battle-start encounter candidate missing required field {key!r}")

rebuilt = sim.rebuild_battle_start(0, False, -1)
if not isinstance(rebuilt, dict):
    fail("StepSimulator.rebuild_battle_start() must return a dict snapshot")
if rebuilt.get("screen_state") != "BATTLE" or not rebuilt.get("battle_active"):
    fail("StepSimulator.rebuild_battle_start() must preserve an active battle")

search = sim.battle_search(3, False)
if not isinstance(search, dict):
    fail("StepSimulator.battle_search() must return a dict")
if search.get("schema_id") != "native-battle-search-root-v1":
    fail("native battle search schema id mismatch")
if search.get("native_api") != "StepSimulator.battle_search.v1":
    fail("native battle search api id mismatch")
if search.get("patch_identity") != "sts_lightspeed_battle_search_root_v1":
    fail("native battle search patch identity mismatch")
if search.get("information_regime") != "full_simulator_state_oracle_like":
    fail("native battle search information regime mismatch")
if search.get("simulations_requested") != 3:
    fail("native battle search simulations_requested mismatch")
if not isinstance(search.get("native_simulator_steps"), int):
    fail("native battle search simulator step count is missing")
root_rows = search.get("root_rows")
if not isinstance(root_rows, list) or not root_rows:
    fail("native battle search root_rows must be a non-empty list")
required_root_fields = {
    "scope",
    "bits",
    "kind",
    "label",
    "search_tree_present",
    "visits",
    "evaluation_sum",
    "mean_value",
}
if not required_root_fields.issubset(root_rows[0]):
    missing_fields = sorted(required_root_fields.difference(root_rows[0]))
    fail("native battle search root row missing fields: " + ", ".join(missing_fields))

battle_actions = sim.legal_actions()
if not isinstance(battle_actions, list) or not battle_actions:
    fail("StepSimulator.legal_actions() must return battle actions before root-prior search")
root_priors = [1.0 for _ in battle_actions]
root_prior_search = sim.battle_search_with_root_priors(
    6,
    False,
    root_priors,
    1.0,
    1,
    1.0,
)
if not isinstance(root_prior_search, dict):
    fail("StepSimulator.battle_search_with_root_priors() must return a dict")
if root_prior_search.get("schema_id") != "native-battle-search-root-v1":
    fail("native root-prior search schema id mismatch")
if (
    root_prior_search.get("native_api")
    != "StepSimulator.battle_search_with_root_priors.v1"
):
    fail("native root-prior search api id mismatch")
if (
    root_prior_search.get("patch_identity")
    != "sts_lightspeed_root_prior_allocation_v1"
):
    fail("native root-prior search patch identity mismatch")
metadata = root_prior_search.get("allocation_metadata")
if not isinstance(metadata, dict):
    fail("native root-prior search allocation_metadata is missing")
if metadata.get("schema_id") != "native-root-prior-allocation-metadata-v1":
    fail("native root-prior allocation metadata schema mismatch")
if metadata.get("allocation_strategy") != "root_prior_mixture_v1":
    fail("native root-prior allocation strategy mismatch")
if metadata.get("allocated_root_visits") != 6:
    fail("native root-prior allocated_root_visits mismatch")
root_prior_rows = root_prior_search.get("root_rows")
if not isinstance(root_prior_rows, list) or not root_prior_rows:
    fail("native root-prior search root_rows must be a non-empty list")
if "allocated_root_visits" not in root_prior_rows[0]:
    fail("native root-prior root row missing allocated_root_visits")
if "root_prior" not in root_prior_rows[0]:
    fail("native root-prior root row missing root_prior")

expected_capabilities = set(manifest.capability_ids)
observed_capabilities = {
    "step_simulation",
    "checkpoint_capture_restore",
    "battle_start_metadata",
    "run_potion_snapshot",
    "non_combat_potion_actions",
    "gcc15_build_compatibility",
    "native_public_projection",
    "native_battle_search_root",
    "native_root_prior_allocation",
    "native_terminal_resource_identity",
    "constructed_battle_start_transforms",
}
missing = sorted(observed_capabilities.difference(expected_capabilities))
if missing:
    fail("manifest omitted verified capabilities: " + ", ".join(missing))

print("native API capability assertions passed")
PY

echo "clean sts_lightspeed pinned-source build passed"
