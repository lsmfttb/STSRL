#!/usr/bin/env bash
# Verify that a proposed sts_lightspeed manifest commit advances the single
# accepted STSRL simulator lineage.

set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 /path/to/sts_lightspeed-checkout <previous-integration-commit> [manifest.json]" >&2
    exit 2
fi

source_checkout=$(cd "$1" && pwd)
previous_commit="$2"
repo_root=$(cd "$(dirname "$0")/.." && pwd)
manifest_path="${3:-$repo_root/docs/sts_lightspeed_source_manifest.json}"

if [[ ! "$previous_commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "previous integration commit must be a 40-character lowercase git commit" >&2
    exit 2
fi

if ! git -C "$source_checkout" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "not a git checkout: $source_checkout" >&2
    exit 2
fi

mapfile -t manifest_values < <(
    python3 - "$manifest_path" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
integration = payload.get("integration")
if not isinstance(integration, dict):
    raise SystemExit("manifest integration must be an object")
for key in ("repository_url", "branch", "ref", "commit"):
    value = integration.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"manifest integration.{key} must be a non-empty string")
    print(value)
PY
)

if [[ ${#manifest_values[@]} -ne 4 ]]; then
    echo "manifest integration metadata is incomplete" >&2
    exit 2
fi

integration_url="${manifest_values[0]}"
integration_branch="${manifest_values[1]}"
integration_ref="${manifest_values[2]}"
integration_commit="${manifest_values[3]}"

if [[ "$integration_branch" != "stsrl/main" ]]; then
    echo "manifest integration branch must be stsrl/main, got: $integration_branch" >&2
    exit 1
fi
if [[ "$integration_ref" != "refs/heads/stsrl/main" ]]; then
    echo "manifest integration ref must be refs/heads/stsrl/main, got: $integration_ref" >&2
    exit 1
fi
if [[ ! "$integration_commit" =~ ^[0-9a-f]{40}$ ]]; then
    echo "manifest integration commit must be a 40-character lowercase git commit" >&2
    exit 2
fi

echo "sts_lightspeed lineage gate"
echo "previous:    $previous_commit"
echo "integration: $integration_url $integration_ref @ $integration_commit"

if ! git -C "$source_checkout" fetch --no-tags "$integration_url" "$integration_ref"; then
    echo "failed to fetch active sts_lightspeed integration ref" >&2
    exit 1
fi

active_commit=$(git -C "$source_checkout" rev-parse FETCH_HEAD^{commit})
if [[ "$active_commit" != "$integration_commit" ]]; then
    echo "active stsrl/main resolves to $active_commit, manifest pins $integration_commit" >&2
    exit 1
fi

if ! git -C "$source_checkout" cat-file -e "$previous_commit^{commit}" 2>/dev/null; then
    echo "previous accepted integration commit is unavailable locally: $previous_commit" >&2
    echo "the proposed active line cannot be proven to descend from it" >&2
    exit 1
fi

if ! git -C "$source_checkout" merge-base --is-ancestor "$previous_commit" "$integration_commit"; then
    echo "lineage violation: proposed integration commit does not descend from previous accepted commit" >&2
    exit 1
fi

echo "lineage: PASS ($previous_commit -> $integration_commit on refs/heads/stsrl/main)"
