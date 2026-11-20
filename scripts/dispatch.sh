#!/usr/bin/env bash
# Reliable trigger. Call this from any external scheduler.
# Requires GH_TOKEN with actions:write.
set -euo pipefail
OWNER="${OWNER:-jacksonjp0311-gif}"
REPO="${REPO:-NOMAD}"
MODE="${1:-awake}"
if [[ "$MODE" == "sleep" ]]; then
  TYPE="sleep"
else
  TYPE="awake"
fi
gh api -X POST "repos/${OWNER}/${REPO}/dispatches" \
  -f event_type="$TYPE" \
  --silent
echo "dispatched $TYPE"
