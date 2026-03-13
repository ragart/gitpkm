#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$REPO_ROOT"

echo "[pkm bootstrap] Installing git hooks"
bash "$REPO_ROOT/scripts/setup/install_hooks.sh"

echo "[pkm bootstrap] Running full pipeline"
bash "$REPO_ROOT/scripts/runtime/pkm_python.sh" "$REPO_ROOT/scripts/automation/run_all.py"

echo "[pkm bootstrap] Done"
