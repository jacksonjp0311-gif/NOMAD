#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v gh >/dev/null || { echo 'Install GitHub CLI (gh) and authenticate' >&2; exit 1; }
command -v git >/dev/null || { echo 'Install git' >&2; exit 1; }
python -B scripts/verify_package_v18.py --require-release
echo 'No automatic publication. Review the exact commit, visibility, and artifact hashes with the repository owner.' >&2
exit 3
