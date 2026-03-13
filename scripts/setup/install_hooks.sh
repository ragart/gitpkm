#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

git -C "$REPO_ROOT" config core.hooksPath .githooks
echo "Git hooks path configured to .githooks"
echo "Pre-commit hook will run: scripts/runtime/pkm_python.sh scripts/automation/run_all.py"
echo "Optional runtime settings can be configured in .env (PKM_CONDA_ENV, PKM_PYTHON_BIN)."
