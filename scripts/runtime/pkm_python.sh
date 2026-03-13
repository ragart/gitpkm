#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SETTINGS_FILE="$REPO_ROOT/.env"

if [[ -f "$SETTINGS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SETTINGS_FILE"
  set +a
fi

PYTHON_BIN="${PKM_PYTHON_BIN:-python3}"
CONDA_ENV="${PKM_CONDA_ENV:-}"

if [[ -z "$CONDA_ENV" ]]; then
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    exec "$PYTHON_BIN" "$@"
  fi

  if [[ "$PYTHON_BIN" != "python3" ]] && command -v python3 >/dev/null 2>&1; then
    exec python3 "$@"
  fi

  if command -v python >/dev/null 2>&1; then
    exec python "$@"
  fi

  echo "[pkm] Python not found in PATH."
  exit 1
fi

if [[ "${CONDA_DEFAULT_ENV:-}" == "$CONDA_ENV" ]]; then
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    exec "$PYTHON_BIN" "$@"
  fi
  echo "[pkm] Conda env '$CONDA_ENV' is active but python binary '$PYTHON_BIN' is not available."
  exit 1
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "[pkm] PKM_CONDA_ENV is set to '$CONDA_ENV' but conda is not available in PATH."
  exit 1
fi

if ! conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
  echo "[pkm] Conda env '$CONDA_ENV' does not exist."
  exit 1
fi

exec conda run -n "$CONDA_ENV" "$PYTHON_BIN" "$@"
