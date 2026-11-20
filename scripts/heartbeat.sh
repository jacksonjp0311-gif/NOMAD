#!/usr/bin/env bash
# NOMAD heartbeat. Keeps the awake -> sleep -> awake chain alive on GitHub
# runners without relying on cron alone (cron stays as a fallback restart).
#
#   heartbeat.sh chain <target-workflow-file> <min-gap-minutes>
#       Dispatch the next link unless a run of the target is already queued
#       or in progress. Waits until <min-gap> minutes have passed since the
#       target's last run was created, so the chain cannot spin tightly.
#   heartbeat.sh watch <stale-minutes>
#       If the body lease heartbeat is older than <stale-minutes> and no body
#       run is queued or running, re-dispatch nomad-body and log the gap.
#
# Needs GH_TOKEN (the job's GITHUB_TOKEN with actions: write) and GITHUB_REPOSITORY.
set -euo pipefail
REPO="${GITHUB_REPOSITORY:-jacksonjp0311-gif/NOMAD}"
AWAKE=continuous-awake.yml
SLEEP=continuous-sleep.yml

active() {  # count queued/in-progress/waiting runs of a workflow
  local wf="$1" n=0 s
  for s in queued in_progress waiting pending requested; do
    n=$(( n + $(gh run list -R "$REPO" -w "$wf" -s "$s" -L 20 --json databaseId -q 'length' 2>/dev/null || echo 0) ))
  done
  echo "$n"
}

epoch() { date -u -d "$1" +%s; }

case "${1:-}" in
  chain)
    target="$2"; gap_min="${3:-15}"
    if [[ "$(active "$target")" -gt 0 ]]; then
      echo "heartbeat: $target already queued/running; chain stays single"; exit 0
    fi
    last=$(gh run list -R "$REPO" -w "$target" -L 1 --json createdAt -q '.[0].createdAt // empty')
    if [[ -n "$last" ]]; then
      wait_s=$(( gap_min * 60 - ( $(date -u +%s) - $(epoch "$last") ) ))
      if (( wait_s > 0 )); then
        echo "heartbeat: not before gap; waiting ${wait_s}s"; sleep "$wait_s"
      fi
    fi
    if [[ "$(active "$target")" -gt 0 ]]; then
      echo "heartbeat: $target started meanwhile; not dispatching"; exit 0
    fi
    gh workflow run "$target" -R "$REPO" --ref main
    echo "heartbeat: dispatched $target"
    ;;
  watch)
    # Primary: the long-lived body. Restart it when its lease heartbeat is
    # older than <stale-minutes> and no body run is queued or running.
    stale_min="${2:-30}"
    read -r alive age < <(python -c "import json,sys; from nomad import lease; l=lease.read(); a=lease.age_min(l); print('true' if lease.alive(l, $stale_min) else 'false', int(a) if a is not None else 99999)")
    echo "heartbeat-watch: body lease alive=${alive} age=${age} min"
    if [[ "$alive" == "true" ]]; then exit 0; fi
    if [[ "$(active nomad-body.yml)" -gt 0 ]]; then
      echo "heartbeat-watch: a body run is queued/running; leaving it"; exit 0
    fi
    gh workflow run nomad-body.yml -R "$REPO" --ref main
    echo "heartbeat-watch: re-dispatched nomad-body"
    echo "GAP_MINUTES=${age}" >> "${GITHUB_ENV:-/dev/null}"
    ;;
  *)
    echo "usage: heartbeat.sh chain <workflow> <gap-min> | watch <stale-min>" >&2; exit 2;;
esac
