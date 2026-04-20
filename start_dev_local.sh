#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-18080}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5180}"

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

cleanup() {
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "[dev] starting backend on http://${API_HOST}:${API_PORT}"
(
  cd "$ROOT_DIR"
  "$PYTHON_CMD" -m uvicorn apps.api.serve:app --host "$API_HOST" --port "$API_PORT"
) &
BACKEND_PID=$!

echo "[dev] starting frontend on http://${WEB_HOST}:${WEB_PORT}"
(
  cd "$ROOT_DIR/frontend/task_center"
  npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT"
) &
FRONTEND_PID=$!

echo "[dev] frontend: http://${WEB_HOST}:${WEB_PORT}"
echo "[dev] backend:  http://${API_HOST}:${API_PORT}"

wait -n "$BACKEND_PID" "$FRONTEND_PID"
