#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-18080}"
UVICORN_WORKERS="${UVICORN_WORKERS:-2}"

resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return
  fi
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return
  fi
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT_DIR/.venv/Scripts/python.exe"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  echo "python"
}

PYTHON_CMD="$(resolve_python)"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Please install Node.js first."
  exit 1
fi

echo "[prod] building frontend bundle and publishing to runtime/webui (with api/webui fallback) ..."
(
  cd "$ROOT_DIR/frontend/task_center"
  npm run build
)

echo "[prod] starting backend on http://${API_HOST}:${API_PORT}"
cd "$ROOT_DIR"
exec "$PYTHON_CMD" -m uvicorn apps.api.serve:app \
  --app-dir "$ROOT_DIR" \
  --host "$API_HOST" \
  --port "$API_PORT" \
  --workers "$UVICORN_WORKERS" \
  --proxy-headers
