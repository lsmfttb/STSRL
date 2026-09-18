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

repo_root=$(cd "$(dirname "$0")/.." && pwd)
: "${T092_FORMAL_RESOURCE_MEMORY_BUDGET_MIB:?set 16384 approved aggregate MiB budget}"
: "${T092_FORMAL_RESOURCE_MEMORY_REQUEST_MIB:?set 2048 approved per-worker MiB request}"
: "${T092_FORMAL_RESOURCE_RUNTIME_RSS_LIMIT_MIB:?set 2048 approved RSS MiB limit}"
: "${T092_FORMAL_RESOURCE_MEMAVAILABLE_FLOOR_MIB:?set 8000 approved MemAvailable MiB floor}"
: "${T092_FORMAL_STATUS_WAIT_SECONDS:=7200}"

wait_for_success() {
  local status_path=$1
  local deadline=$((SECONDS + T092_FORMAL_STATUS_WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if [[ -f $status_path ]]; then
      local state
      state=$(/usr/bin/python3.14 - "$status_path" <<'PY'
import json
import sys
try:
    value = json.load(open(sys.argv[1], encoding="utf-8"))
    state = value.get("state") if isinstance(value, dict) else None
    print(state if state in {"RUNNING", "SUCCEEDED", "FAILED"} else "INVALID")
except (OSError, ValueError):
    print("INVALID")
PY
)
      if [[ $state == SUCCEEDED ]]; then
        return 0
      fi
      if [[ $state != RUNNING ]]; then
        echo "formal shard status failed closed: $status_path ($state)" >&2
        return 1
      fi
    fi
    sleep 2
  done
  echo "formal shard status timed out or was never created: $status_path" >&2
  return 1
}

for shard in $(seq 0 7); do
  python3 "$repo_root/scripts/run_detached_job.py" start \
    --status "$ARTIFACT_ROOT/jobs/t092-formal-shard-${shard}.status.json" \
    --stdout "$ARTIFACT_ROOT/jobs/t092-formal-shard-${shard}.stdout.log" \
    --stderr "$ARTIFACT_ROOT/jobs/t092-formal-shard-${shard}.stderr.log" \
    --cwd "$repo_root" --expected-seconds 3600 \
    --resource-root "$ARTIFACT_ROOT/resource-admission" \
    --resource-memory-budget-mib "$T092_FORMAL_RESOURCE_MEMORY_BUDGET_MIB" \
    --resource-memory-request-mib "$T092_FORMAL_RESOURCE_MEMORY_REQUEST_MIB" \
    --resource-runtime-rss-limit-mib "$T092_FORMAL_RESOURCE_RUNTIME_RSS_LIMIT_MIB" \
    --resource-runtime-memavailable-floor-mib "$T092_FORMAL_RESOURCE_MEMAVAILABLE_FLOOR_MIB" \
    --resource-batch-id "t092-formal-${HEAD}" --resource-job-id "t092-formal-shard-${shard}" \
    --resource-wait-seconds 3600 --resource-stage t092-formal-telemetry \
    --resource-worker-count 8 --resource-shard-count 8 -- \
    env PYTHONPATH=src /usr/bin/python3.14 -m sts_combat_rl.commands.t092_formal run-shard \
      --authorization "$AUTH" --implementation-head "$HEAD" --split-manifest "$SPLIT" \
      --root-reference "$ROOT_REFERENCE" --canary-evidence-reference "$CANARY_REFERENCE" \
      --input-identities "$INPUT_IDENTITIES" --artifact-root "$ARTIFACT_ROOT" \
      --output "$ARTIFACT_ROOT/shards/shard-$(printf '%02d' "$shard").json" \
      --shard-index "$shard" \
      --runtime-factory sts_combat_rl.commands.t092_formal_runtime:t092_formal_runtime
done

for shard in $(seq 0 7); do
  wait_for_success "$ARTIFACT_ROOT/jobs/t092-formal-shard-${shard}.status.json"
done

args=()
for shard in $(seq 0 7); do
  args+=(--shard "$ARTIFACT_ROOT/shards/shard-$(printf '%02d' "$shard").json")
done
env PYTHONPATH=src /usr/bin/python3.14 -m sts_combat_rl.commands.t092_formal finalize \
  --authorization "$AUTH" --implementation-head "$HEAD" --split-manifest "$SPLIT" \
  --root-reference "$ROOT_REFERENCE" --canary-evidence-reference "$CANARY_REFERENCE" \
  --input-identities "$INPUT_IDENTITIES" --artifact-root "$ARTIFACT_ROOT" \
  --output "$ARTIFACT_ROOT/t092-formal-evidence.json" "${args[@]}"
