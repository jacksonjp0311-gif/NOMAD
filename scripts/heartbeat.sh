#!/usr/bin/env bash
# NOMAD heartbeat. Keeps the awake -> sleep -> awake chain alive on GitHub
# runners without relying on cron alone (cron stays as a fallback restart).
#
#   heartbeat.sh chain <target-workflow-file> <min-gap-minutes>
#       Dispatch the next link unless a run of the target is already queued
#       or in progress. Waits until <min-gap> minutes have passed since the
#       target's last run was created, so the chain cannot spin tightly.
#   heartbeat.sh watch <stale-minutes>
#       If no awake run succeeded in <stale-minutes> and nothing is queued or
#       running, re-dispatch awake and log the gap to the organism health file.
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
    stale_min="${2:-90}"
    last_ok=$(gh run list -R "$REPO" -w "$AWAKE" -s success -L 1 --json updatedAt -q '.[0].updatedAt // empty')
    now=$(date -u +%s)
    if [[ -z "$last_ok" ]]; then gap_min=99999; else gap_min=$(( (now - $(epoch "$last_ok")) / 60 )); fi
    echo "heartbeat-watch: last successful awake ${gap_min} min ago"
    if (( gap_min < stale_min )); then exit 0; fi
    if [[ "$(active "$AWAKE")" -gt 0 || "$(active "$SLEEP")" -gt 0 ]]; then
      echo "heartbeat-watch: stale but a run is queued/running; leaving it"; exit 0
    fi
    gh workflow run "$AWAKE" -R "$REPO" --ref main
    echo "heartbeat-watch: re-dispatched $AWAKE"
    echo "GAP_MINUTES=${gap_min}" >> "${GITHUB_ENV:-/dev/null}"
    ;;
  *)
    echo "usage: heartbeat.sh chain <workflow> <gap-min> | watch <stale-min>" >&2; exit 2;;
esac
