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
git submodule update --init "${submodules[@]}"
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
):
    if key not in snapshot:
        fail(f"snapshot missing required field {key!r}")

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

expected_capabilities = set(manifest.capability_ids)
observed_capabilities = {
    "step_simulation",
    "checkpoint_capture_restore",
    "battle_start_metadata",
    "run_potion_snapshot",
    "non_combat_potion_actions",
    "gcc15_build_compatibility",
    "native_public_projection",
}
missing = sorted(observed_capabilities.difference(expected_capabilities))
if missing:
    fail("manifest omitted verified capabilities: " + ", ".join(missing))

print("native API capability assertions passed")
PY

echo "clean sts_lightspeed pinned-source build passed"
