#!/usr/bin/env bash
# Start the twelve authorized T092 paired-canary shards as detached jobs.
# This launcher is intentionally inert unless a separately approved exact-head
# authorization file is supplied to the real execution command.
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

for shard_index in $(seq 0 11); do
  shard_root="$artifact_root/shards"
  job_root="$artifact_root/jobs"
  python3 "$repo_root/scripts/run_detached_job.py" start \
    --status "$job_root/t092-canary-shard-${shard_index}.status.json" \
    --stdout "$job_root/t092-canary-shard-${shard_index}.stdout.log" \
    --stderr "$job_root/t092-canary-shard-${shard_index}.stderr.log" \
    --cwd "$repo_root" \
    --expected-seconds 900 \
    -- env PYTHONPATH=src python3 -m sts_combat_rl.commands.t092_canary_execution run-shard \
      --implementation-head "$implementation_head" \
      --authorization "$authorization" \
      --split-manifest "$split_manifest" \
      --runtime-input-identities "$runtime_input_identities" \
      --runtime-factory "$runtime_factory" \
      --artifact-root "$artifact_root" \
      --shard-index "$shard_index" \
      --output "$shard_root/t092-canary-shard-${shard_index}.json"
done
