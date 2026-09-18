#!/usr/bin/env bash
# Start the twelve authorized T092 paired-canary shards as detached jobs.
# This launcher is intentionally inert unless a separately approved exact-head
# authorization file is supplied to the real execution command.  Its runtime
# input map must already bind one private selected-12 restore payload produced
# by `prepare-restore-inputs`; do not let every shard re-admit full T087/T085.
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: $0 <implementation-head> <authorization.json> <split-manifest.json> <runtime-input-identities.json> <runtime-factory> <artifact-root>" >&2
  exit 2
fi

implementation_head=$1
authorization=$2
split_manifest=$3
runtime_input_identities=$4
runtime_factory=$5
artifact_root=$6
repo_root=$(cd "$(dirname "$0")/.." && pwd)

# The twelve logical shard positions are not permission to run twelve resident
# simulator processes.  The separately reviewed resource values must be based
# on the compact-admission record and the authorized canary calibration plan.
: "${T092_CANARY_RESOURCE_MEMORY_BUDGET_MIB:?set an approved aggregate MiB budget}"
: "${T092_CANARY_RESOURCE_MEMORY_REQUEST_MIB:?set an approved per-shard MiB request}"
: "${T092_CANARY_RESOURCE_RUNTIME_RSS_LIMIT_MIB:?set an approved per-shard RSS limit}"
: "${T092_CANARY_RESOURCE_MEMAVAILABLE_FLOOR_MIB:?set an approved MemAvailable floor}"

for shard_index in $(seq 0 11); do
  shard_root="$artifact_root/shards"
  job_root="$artifact_root/jobs"
  python3 "$repo_root/scripts/run_detached_job.py" start \
    --status "$job_root/t092-canary-shard-${shard_index}.status.json" \
    --stdout "$job_root/t092-canary-shard-${shard_index}.stdout.log" \
    --stderr "$job_root/t092-canary-shard-${shard_index}.stderr.log" \
    --cwd "$repo_root" \
    --expected-seconds 900 \
    --resource-root "$artifact_root/resource-admission" \
    --resource-memory-budget-mib "$T092_CANARY_RESOURCE_MEMORY_BUDGET_MIB" \
    --resource-memory-request-mib "$T092_CANARY_RESOURCE_MEMORY_REQUEST_MIB" \
    --resource-runtime-rss-limit-mib "$T092_CANARY_RESOURCE_RUNTIME_RSS_LIMIT_MIB" \
    --resource-runtime-memavailable-floor-mib "$T092_CANARY_RESOURCE_MEMAVAILABLE_FLOOR_MIB" \
    --resource-batch-id "t092-canary-${implementation_head}" \
    --resource-job-id "t092-canary-shard-${shard_index}" \
    --resource-wait-seconds 3600 \
    --resource-stage t092-canary-process-isolated \
    --resource-worker-count 12 \
    --resource-shard-count 12 \
    -- env PYTHONPATH=src /usr/bin/python3.14 -m sts_combat_rl.commands.t092_canary_execution run-shard \
      --implementation-head "$implementation_head" \
      --authorization "$authorization" \
      --split-manifest "$split_manifest" \
      --runtime-input-identities "$runtime_input_identities" \
      --runtime-factory "$runtime_factory" \
      --artifact-root "$artifact_root" \
      --shard-index "$shard_index" \
      --output "$shard_root/t092-canary-shard-${shard_index}.json"
done
