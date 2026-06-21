#!/usr/bin/env bash
# Verify the canonical external simulator patch stack in an isolated worktree.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/sts_lightspeed-checkout" >&2
    exit 2
fi

source_checkout=$(cd "$1" && pwd)
repo_root=$(cd "$(dirname "$0")/.." && pwd)
base_commit="7476a81"
worktree=$(mktemp -d "${TMPDIR:-/tmp}/stsrl-patch-stack.XXXXXX")

cleanup() {
    git -C "$source_checkout" worktree remove --force "$worktree" >/dev/null 2>&1 || true
    git -C "$source_checkout" worktree prune
}
trap cleanup EXIT

git -C "$source_checkout" worktree add --detach "$worktree" "$base_commit" >/dev/null

cd "$worktree"
git apply --index "$repo_root/patches/sts_lightspeed_pybind11_v304.patch"
git submodule update --init json pybind11

for patch in \
    sts_lightspeed_step_simulator.patch \
    sts_lightspeed_checkpoint_restore.patch \
    sts_lightspeed_battle_start_metadata.patch \
    sts_lightspeed_public_run_context.patch \
    sts_lightspeed_run_potion_snapshot.patch \
    sts_lightspeed_non_combat_potion_actions.patch \
    sts_lightspeed_gcc15_compat.patch; do
    git apply "$repo_root/patches/$patch"
done

cmake -S . -B build-t004-py -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build build-t004-py --target slaythespire -j 2
PYTHONPATH="$worktree/build-t004-py" python3 -c \
    "import slaythespire; assert hasattr(slaythespire.StepSimulator, 'capture_checkpoint')"

echo "clean sts_lightspeed patch-stack build passed"
