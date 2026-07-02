#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
OUT="${OUT:-/mnt/d/DeadlycatCoding/STSRL/artifacts/t051-search-controlled-later-act-source-collection-pr}"
PY="${PY:-/home/lsmft/stsrl-spikes/py313-torch/bin/python}"
BUILD="${BUILD:-/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch}"
CHECKPOINT="${CHECKPOINT:-/mnt/d/DeadlycatCoding/STSRL/artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt}"

TOTAL_RUNS="${TOTAL_RUNS:-1000}"
SOURCE_SEED_START="${SOURCE_SEED_START:-1}"
SHARDS="${SHARDS:-16}"
WORKERS="${WORKERS:-16}"
NON_COMBAT_SEED="${NON_COMBAT_SEED:-42050}"
STEP_CAP="${STEP_CAP:-500}"
BUDGET="${BUDGET:-20}"
ROOT_SELECTION="${ROOT_SELECTION:-highest_mean}"
ASCENSION="${ASCENSION:-20}"
TASK_ID="${TASK_ID:-T051}"

if (( TOTAL_RUNS < 1 )); then
  echo "TOTAL_RUNS must be positive" >&2
  exit 2
fi
if (( SHARDS < 1 )); then
  echo "SHARDS must be positive" >&2
  exit 2
fi
if (( WORKERS < 1 )); then
  echo "WORKERS must be positive" >&2
  exit 2
fi
if (( SHARDS > TOTAL_RUNS )); then
  echo "SHARDS must not exceed TOTAL_RUNS" >&2
  exit 2
fi

mkdir -p "$OUT"
: > "$OUT/stage-times.tsv"

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }

shard_start_count() {
  local idx="$1"
  local base=$((TOTAL_RUNS / SHARDS))
  local rem=$((TOTAL_RUNS % SHARDS))
  local count="$base"
  local extra_before="$rem"
  if (( idx < rem )); then
    count=$((base + 1))
    extra_before="$idx"
  fi
  local start=$((SOURCE_SEED_START + idx * base + extra_before))
  printf '%s %s\n' "$start" "$count"
}

wait_for_slot() {
  while (( $(jobs -pr | wc -l) >= WORKERS )); do
    if ! wait -n; then
      wait || true
      return 1
    fi
  done
}

wait_for_all() {
  local status=0
  while (( $(jobs -pr | wc -l) > 0 )); do
    if ! wait -n; then
      status=1
    fi
  done
  return "$status"
}

run_source_shard() {
  local arm="$1" controller="$2" idx="$3" start_seed="$4" count="$5"
  local shard_dir="$OUT/$arm/source-shards/shard-$idx"
  mkdir -p "$shard_dir"
  local args=(
    -m sts_combat_rl.cli
    --lightspeed-search-battle-start-pool "$shard_dir/pool.jsonl"
    --search-battle-controller "$controller"
    --sim-seed "$start_seed"
    --sim-episodes "$count"
    --sim-ascension "$ASCENSION"
    --sim-steps "$STEP_CAP"
    --search-budget "$BUDGET"
    --oracle-root-selection "$ROOT_SELECTION"
    --sim-non-combat-policy stochastic-v1
    --sim-non-combat-seed "$NON_COMBAT_SEED"
    --log-file "$shard_dir/source.log"
  )
  if [[ "$controller" != "oracle_search_v1" ]]; then
    args+=(--model-guided-oracle-checkpoint "$CHECKPOINT")
  fi
  PYTHONPATH="$BUILD:$REPO/src" "$PY" "${args[@]}" \
    > "$shard_dir/source.out" 2> "$shard_dir/source.err"
}

run_coverage_shard() {
  local arm="$1" idx="$2"
  local source_pool="$OUT/$arm/source-shards/shard-$idx/pool.jsonl"
  local shard_dir="$OUT/$arm/coverage-shards"
  mkdir -p "$shard_dir"
  PYTHONPATH="$BUILD:$REPO/src" "$PY" -m sts_combat_rl.cli \
    --lightspeed-a20-battle-start-coverage "$source_pool" \
    --a20-coverage-output "$shard_dir/shard-$idx.json" \
    --battle-start-restore-limit 0 \
    --pytorch-gate-required-ascensions "$ASCENSION" \
    --pytorch-gate-required-acts 1 2 3 4 \
    --log-file "$shard_dir/shard-$idx.log" \
    > "$shard_dir/shard-$idx.out" 2> "$shard_dir/shard-$idx.err"
}

run_arm() {
  local arm="$1" controller="$2"
  local arm_dir="$OUT/$arm"
  local seed_end=$((SOURCE_SEED_START + TOTAL_RUNS - 1))
  mkdir -p "$arm_dir/source-shards" "$arm_dir/coverage-shards"

  log "source collection start arm=$arm controller=$controller workers=$WORKERS shards=$SHARDS seeds=$SOURCE_SEED_START..$seed_end"
  local start_ts
  start_ts=$(date +%s)
  local idx start_seed count
  for idx in $(seq 0 $((SHARDS - 1))); do
    read -r start_seed count < <(shard_start_count "$idx")
    wait_for_slot
    run_source_shard "$arm" "$controller" "$idx" "$start_seed" "$count" &
  done
  wait_for_all
  local elapsed=$(( $(date +%s) - start_ts ))
  printf '%s\tsource_collection\t%s\t%s\t%s..%s\t%s\n' "$arm" "$WORKERS" "$SHARDS" "$SOURCE_SEED_START" "$seed_end" "$elapsed" >> "$OUT/stage-times.tsv"
  log "source collection done arm=$arm elapsed=${elapsed}s"

  local -a pool_args=()
  for idx in $(seq 0 $((SHARDS - 1))); do
    pool_args+=(--battle-start-pool-shard "$arm_dir/source-shards/shard-$idx/pool.jsonl")
  done
  start_ts=$(date +%s)
  PYTHONPATH="$REPO/src" "$PY" -m sts_combat_rl.cli \
    --merge-battle-start-pool-shards "$arm_dir/merged-pool.jsonl" \
    "${pool_args[@]}" \
    --battle-start-pool-shard-merge-manifest "$arm_dir/source-merge-manifest.json" \
    --log-file - \
    > "$arm_dir/source-merge.out" 2> "$arm_dir/source-merge.err"
  elapsed=$(( $(date +%s) - start_ts ))
  printf '%s\tsource_merge\t1\t%s\t%s..%s\t%s\n' "$arm" "$SHARDS" "$SOURCE_SEED_START" "$seed_end" "$elapsed" >> "$OUT/stage-times.tsv"
  log "source merge done arm=$arm elapsed=${elapsed}s"

  log "coverage restore start arm=$arm workers=$WORKERS shards=$SHARDS"
  start_ts=$(date +%s)
  for idx in $(seq 0 $((SHARDS - 1))); do
    wait_for_slot
    run_coverage_shard "$arm" "$idx" &
  done
  wait_for_all
  elapsed=$(( $(date +%s) - start_ts ))
  printf '%s\tcoverage_restore\t%s\t%s\t%s..%s\t%s\n' "$arm" "$WORKERS" "$SHARDS" "$SOURCE_SEED_START" "$seed_end" "$elapsed" >> "$OUT/stage-times.tsv"
  log "coverage restore done arm=$arm elapsed=${elapsed}s"

  local -a coverage_args=()
  for idx in $(seq 0 $((SHARDS - 1))); do
    coverage_args+=(--battle-start-coverage-shard "$arm_dir/coverage-shards/shard-$idx.json")
  done
  start_ts=$(date +%s)
  PYTHONPATH="$REPO/src" "$PY" -m sts_combat_rl.cli \
    --merge-a20-battle-start-coverage "$arm_dir/merged-coverage.json" \
    --merged-battle-start-pool "$arm_dir/merged-pool.jsonl" \
    "${coverage_args[@]}" \
    --battle-start-restore-limit 0 \
    --pytorch-gate-required-ascensions "$ASCENSION" \
    --pytorch-gate-required-acts 1 2 3 4 \
    --log-file - \
    > "$arm_dir/coverage-merge.out" 2> "$arm_dir/coverage-merge.err"
  elapsed=$(( $(date +%s) - start_ts ))
  printf '%s\tcoverage_merge\t1\t%s\t%s..%s\t%s\n' "$arm" "$SHARDS" "$SOURCE_SEED_START" "$seed_end" "$elapsed" >> "$OUT/stage-times.tsv"
  log "coverage merge done arm=$arm elapsed=${elapsed}s"
}

run_arm "baseline_oracle_search_v1" "oracle_search_v1"
run_arm "post_search_model_guided_v2" "model_guided_oracle_search_v2"
run_arm "root_prior_guided_v1" "root_prior_guided_oracle_search_v1"

log "reachability report start"
start_ts=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" -m sts_combat_rl.cli \
  --a20-reachability-report "$OUT/reachability-report.json" \
  --stream-reachability-pools \
  --reachability-arm baseline_oracle_search_v1 "$OUT/baseline_oracle_search_v1/merged-pool.jsonl" "$OUT/baseline_oracle_search_v1/merged-coverage.json" \
  --reachability-arm post_search_model_guided_v2 "$OUT/post_search_model_guided_v2/merged-pool.jsonl" "$OUT/post_search_model_guided_v2/merged-coverage.json" \
  --reachability-arm root_prior_guided_v1 "$OUT/root_prior_guided_v1/merged-pool.jsonl" "$OUT/root_prior_guided_v1/merged-coverage.json" \
  --log-file - \
  > "$OUT/reachability.out" 2> "$OUT/reachability.err"
elapsed=$(( $(date +%s) - start_ts ))
seed_end=$((SOURCE_SEED_START + TOTAL_RUNS - 1))
printf '%s\treachability_report\t1\t3\t%s..%s\t%s\n' "all_arms" "$SOURCE_SEED_START" "$seed_end" "$elapsed" >> "$OUT/stage-times.tsv"
log "reachability report done elapsed=${elapsed}s"

PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/summarize_t051_later_act_artifacts.py" \
  --artifact-root "$OUT" \
  --repo "$REPO" \
  --checkpoint "$CHECKPOINT" \
  --runtime-python "$PY" \
  --runtime-build "$BUILD" \
  --task-id "$TASK_ID" \
  --total-runs "$TOTAL_RUNS" \
  --source-seed-start "$SOURCE_SEED_START" \
  --shards "$SHARDS" \
  --workers "$WORKERS" \
  --non-combat-seed "$NON_COMBAT_SEED" \
  --step-cap "$STEP_CAP" \
  --budget "$BUDGET" \
  --root-selection "$ROOT_SELECTION" \
  --output "$OUT/t051-retention-manifest.json"
log "retention manifest written path=$OUT/t051-retention-manifest.json"
