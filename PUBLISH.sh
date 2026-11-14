#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v gh >/dev/null || { echo 'Install GitHub CLI (gh) and authenticate' >&2; exit 1; }
command -v git >/dev/null || { echo 'Install git' >&2; exit 1; }
python -B scripts/verify_package_v17.py --tests --security --smoke
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -b main
git add .
git diff --cached --quiet || git commit -m 'NOMAD v0.17.0 MISSION RUNTIME restartable coding missions'
git branch -M main
if ! git remote get-url origin >/dev/null 2>&1; then
  gh auth status
  gh repo create jacksonjp0311-gif/NOMAD --public --source . --remote origin --push \
    --description 'NOMAD: Bitwork-driven coding intelligence with witnessed evidence'
else
  git push -u origin main
fi
