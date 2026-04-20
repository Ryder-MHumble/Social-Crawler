#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-18080}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5180}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/runtime/logs}"
BACKEND_LOG_PATH="${BACKEND_LOG_PATH:-$LOG_DIR/dev_backend.log}"
FRONTEND_LOG_PATH="${FRONTEND_LOG_PATH:-$LOG_DIR/dev_frontend.log}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-$LOG_DIR/dev_backend.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-$LOG_DIR/dev_frontend.pid}"
TAIL_LINES="${TAIL_LINES:-120}"

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
ACTION="${1:-start}"
if [[ $# -gt 0 ]]; then
  shift
fi

FOLLOW_LOGS=0
ATTACH_START=0

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Please install Node.js first."
  exit 1
fi

mkdir -p "$LOG_DIR"

usage() {
  cat <<EOF
Usage:
  ./start_dev_local.sh start [--attach]
  ./start_dev_local.sh stop
  ./start_dev_local.sh restart [--attach]
  ./start_dev_local.sh status
  ./start_dev_local.sh logs [-f|--follow]

Environment:
  API_HOST/API_PORT WEB_HOST/WEB_PORT
  BACKEND_LOG_PATH FRONTEND_LOG_PATH
  BACKEND_PID_FILE FRONTEND_PID_FILE
EOF
}

pid_from_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file" 2>/dev/null || true
  fi
}

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

start_backend() {
  (
    cd "$ROOT_DIR"
    nohup "$PYTHON_CMD" -m uvicorn apps.api.serve:app --host "$API_HOST" --port "$API_PORT" >>"$BACKEND_LOG_PATH" 2>&1
  ) &
  echo "$!" >"$BACKEND_PID_FILE"
}

start_frontend() {
  (
    cd "$ROOT_DIR/frontend/task_center"
    nohup npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT" >>"$FRONTEND_LOG_PATH" 2>&1
  ) &
  echo "$!" >"$FRONTEND_PID_FILE"
}

stop_pid_file() {
  local pid_file="$1"
  local name="$2"
  local pid

  pid="$(pid_from_file "$pid_file")"
  if ! is_pid_running "$pid"; then
    rm -f "$pid_file"
    echo "[dev] $name not running"
    return 0
  fi

  kill "$pid" >/dev/null 2>&1 || true
  sleep 0.5
  if is_pid_running "$pid"; then
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi

  rm -f "$pid_file"
  echo "[dev] stopped $name (pid=$pid)"
}

status_service() {
  local pid_file="$1"
  local name="$2"
  local pid
  pid="$(pid_from_file "$pid_file")"
  if is_pid_running "$pid"; then
    echo "[dev] $name: running (pid=$pid)"
  else
    echo "[dev] $name: stopped"
  fi
}

start_cmd() {
  local backend_pid frontend_pid
  backend_pid="$(pid_from_file "$BACKEND_PID_FILE")"
  frontend_pid="$(pid_from_file "$FRONTEND_PID_FILE")"

  if is_pid_running "$backend_pid" || is_pid_running "$frontend_pid"; then
    echo "[dev] existing dev services detected, run './start_dev_local.sh restart' or './start_dev_local.sh stop' first."
    exit 1
  fi

  : >"$BACKEND_LOG_PATH"
  : >"$FRONTEND_LOG_PATH"

  echo "[dev] starting backend on http://${API_HOST}:${API_PORT}"
  start_backend
  echo "[dev] starting frontend on http://${WEB_HOST}:${WEB_PORT}"
  start_frontend

  echo "[dev] frontend: http://${WEB_HOST}:${WEB_PORT}"
  echo "[dev] backend:  http://${API_HOST}:${API_PORT}"
  echo "[dev] backend log:  $BACKEND_LOG_PATH"
  echo "[dev] frontend log: $FRONTEND_LOG_PATH"

  if [[ "$ATTACH_START" == "1" ]]; then
    trap 'stop_cmd; exit 0' INT TERM
    logs_cmd_follow
  fi
}

stop_cmd() {
  stop_pid_file "$BACKEND_PID_FILE" "backend"
  stop_pid_file "$FRONTEND_PID_FILE" "frontend"
}

status_cmd() {
  status_service "$BACKEND_PID_FILE" "backend"
  status_service "$FRONTEND_PID_FILE" "frontend"
}

logs_cmd_once() {
  echo "== backend ($BACKEND_LOG_PATH) =="
  if [[ -f "$BACKEND_LOG_PATH" ]]; then
    tail -n "$TAIL_LINES" "$BACKEND_LOG_PATH"
  else
    echo "[dev] backend log file not found"
  fi

  echo
  echo "== frontend ($FRONTEND_LOG_PATH) =="
  if [[ -f "$FRONTEND_LOG_PATH" ]]; then
    tail -n "$TAIL_LINES" "$FRONTEND_LOG_PATH"
  else
    echo "[dev] frontend log file not found"
  fi
}

logs_cmd_follow() {
  touch "$BACKEND_LOG_PATH" "$FRONTEND_LOG_PATH"
  tail -n "$TAIL_LINES" -f "$BACKEND_LOG_PATH" "$FRONTEND_LOG_PATH"
}

logs_cmd() {
  if [[ "$FOLLOW_LOGS" == "1" ]]; then
    logs_cmd_follow
  else
    logs_cmd_once
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -f|--follow)
        FOLLOW_LOGS=1
        ;;
      --attach)
        ATTACH_START=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done
}

parse_args "$@"

case "$ACTION" in
  start)
    start_cmd
    ;;
  stop)
    stop_cmd
    ;;
  restart)
    stop_cmd
    start_cmd
    ;;
  status)
    status_cmd
    ;;
  logs)
    logs_cmd
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown action: $ACTION"
    usage
    exit 1
    ;;
esac
