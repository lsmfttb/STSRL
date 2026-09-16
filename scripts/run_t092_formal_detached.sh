#!/usr/bin/env bash
# Reviewable T092 formal launcher.  It is intentionally inert until supplied
# an exact Maintainer FORMAL_AUTHORIZED JSON; do not use it for canary work.
set -euo pipefail

if [[ $# -ne 8 ]]; then
  echo "usage: $0 AUTH HEAD SPLIT ROOT_REFERENCE CANARY_REFERENCE INPUT_IDENTITIES ARTIFACT_ROOT --formal-authorized" >&2
  exit 64
fi

AUTH=$1
HEAD=$2
SPLIT=$3
ROOT_REFERENCE=$4
CANARY_REFERENCE=$5
INPUT_IDENTITIES=$6
ARTIFACT_ROOT=$7
UNUSED=$8
if [[ $UNUSED != --formal-authorized ]]; then
  echo "refusing to launch without the explicit --formal-authorized acknowledgement" >&2
  exit 64
fi

for shard in $(seq 0 7); do
  python3.14 -m sts_combat_rl.commands.t092_formal run-shard \
    --authorization "$AUTH" --implementation-head "$HEAD" --split-manifest "$SPLIT" \
    --root-reference "$ROOT_REFERENCE" --canary-evidence-reference "$CANARY_REFERENCE" \
    --input-identities "$INPUT_IDENTITIES" --artifact-root "$ARTIFACT_ROOT" \
    --output "$ARTIFACT_ROOT/shards/shard-$(printf '%02d' "$shard").json" \
    --shard-index "$shard" \
    --runtime-factory sts_combat_rl.commands.t092_formal_runtime:t092_formal_runtime &
done
wait

args=()
for shard in $(seq 0 7); do
  args+=(--shard "$ARTIFACT_ROOT/shards/shard-$(printf '%02d' "$shard").json")
done
python3.14 -m sts_combat_rl.commands.t092_formal finalize \
  --authorization "$AUTH" --implementation-head "$HEAD" --split-manifest "$SPLIT" \
  --root-reference "$ROOT_REFERENCE" --canary-evidence-reference "$CANARY_REFERENCE" \
  --input-identities "$INPUT_IDENTITIES" --artifact-root "$ARTIFACT_ROOT" \
  --output "$ARTIFACT_ROOT/t092-formal-evidence.json" "${args[@]}"
