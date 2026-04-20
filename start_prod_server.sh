#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend/task_center"
DEFAULT_PUBLIC_HOST="10.1.132.4"

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-18080}"
UVICORN_WORKERS="${UVICORN_WORKERS:-2}"
UVICORN_EXTRA_ARGS="${UVICORN_EXTRA_ARGS:-}"
PORT_CONFLICT_POLICY="${PORT_CONFLICT_POLICY:-smart}"
API_PORT_SEARCH_LIMIT="${API_PORT_SEARCH_LIMIT:-50}"
PUBLIC_HOST_HINT="${PUBLIC_HOST_HINT:-$DEFAULT_PUBLIC_HOST}"
SKIP_FRONTEND_BUILD="${SKIP_FRONTEND_BUILD:-false}"
AUTO_CREATE_ENV_FILE="${AUTO_CREATE_ENV_FILE:-true}"
AUTO_CREATE_VENV="${AUTO_CREATE_VENV:-true}"
AUTO_INSTALL_BACKEND_DEPS="${AUTO_INSTALL_BACKEND_DEPS:-true}"
AUTO_INSTALL_FRONTEND_DEPS="${AUTO_INSTALL_FRONTEND_DEPS:-true}"
AUTO_INIT_SQLITE="${AUTO_INIT_SQLITE:-true}"
STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC:-45}"
BACKEND_LOG_PATH="${BACKEND_LOG_PATH:-$ROOT_DIR/runtime/logs/prod_server.log}"
PID_FILE="${PID_FILE:-$ROOT_DIR/runtime/logs/prod_server.pid}"

PYTHON_CMD=""
FINAL_API_PORT=""
BACKEND_PID=""
STARTED_BACKEND=0
REUSED_BACKEND=0
CURRENT_SHELL_PGID="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ' || true)"

info() {
  printf '[info] %s\n' "$*"
}

ok() {
  printf '[ok] %s\n' "$*"
}

warn() {
  printf '[warn] %s\n' "$*" >&2
}

die() {
  printf '[error] %s\n' "$*" >&2
  exit 1
}

step() {
  printf '\n==> %s\n' "$*"
}

is_truthy() {
  case "${1,,}" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

load_nvm_if_needed() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return 0
  fi

  local nvm_dir="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$nvm_dir/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    . "$nvm_dir/nvm.sh"
    hash -r
  fi
}

resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
    return 0
  fi
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/Scripts/python.exe"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf 'python3\n'
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf 'python\n'
    return 0
  fi
  return 1
}

require_command() {
  local command_name="$1"
  local help_text="${2:-Install it first and retry.}"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    die "$command_name not found. $help_text"
  fi
}

get_python_version() {
  "$1" - <<'PY'
import sys
print(".".join(str(part) for part in sys.version_info[:3]))
PY
}

assert_python_version() {
  local version="$1"
  local major minor
  IFS='.' read -r major minor _ <<<"$version"
  if (( major < 3 || (major == 3 && minor < 11) )); then
    die "Python >= 3.11 is required, but found $version."
  fi
}

assert_node_version() {
  local version="$1"
  local major="${version%%.*}"
  if [[ ! "$major" =~ ^[0-9]+$ ]]; then
    die "Unable to parse Node.js version: $version"
  fi
  if (( major < 18 )); then
    die "Node.js >= 18 is required, but found $version."
  fi
}

ensure_env_file() {
  if [[ -f "$ROOT_DIR/.env" ]]; then
    ok "Using existing .env file."
    return 0
  fi

  if ! [[ -f "$ROOT_DIR/.env.example" ]]; then
    die ".env is missing and .env.example was not found."
  fi

  if ! is_truthy "$AUTO_CREATE_ENV_FILE"; then
    die ".env is missing. Set AUTO_CREATE_ENV_FILE=true or create it manually."
  fi

  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  ok "Created .env from .env.example."
}

check_env_placeholders() {
  if grep -q 'your-project\.supabase\.co' "$ROOT_DIR/.env" 2>/dev/null; then
    warn "SUPABASE_URL is still using the example placeholder. This is fine unless you use supabase storage."
  fi
  if grep -q 'your_service_role_key' "$ROOT_DIR/.env" 2>/dev/null; then
    warn "SUPABASE_KEY is still using the example placeholder. This is fine unless you use supabase storage."
  fi
}

ensure_virtualenv() {
  local bootstrap_python="$1"
  if [[ -x "$ROOT_DIR/.venv/bin/python" || -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    ok "Using existing virtual environment at $ROOT_DIR/.venv."
    return 0
  fi

  if ! is_truthy "$AUTO_CREATE_VENV"; then
    die "Virtual environment not found. Set AUTO_CREATE_VENV=true or create $ROOT_DIR/.venv manually."
  fi

  step "Creating virtual environment"
  "$bootstrap_python" -m venv "$ROOT_DIR/.venv"
  ok "Created $ROOT_DIR/.venv."
}

ensure_pip() {
  if "$PYTHON_CMD" -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  "$PYTHON_CMD" -m ensurepip --upgrade >/dev/null 2>&1
}

backend_dependencies_ready() {
  "$PYTHON_CMD" - <<'PY' >/dev/null 2>&1
import importlib
modules = ["fastapi", "uvicorn", "dotenv", "yaml", "aiosqlite"]
for module_name in modules:
    importlib.import_module(module_name)
import api.main
PY
}

install_backend_dependencies() {
  if backend_dependencies_ready; then
    ok "Backend Python dependencies are ready."
    return 0
  fi

  if ! is_truthy "$AUTO_INSTALL_BACKEND_DEPS"; then
    die "Backend dependencies are incomplete. Set AUTO_INSTALL_BACKEND_DEPS=true or run '$PYTHON_CMD -m pip install -e .'"
  fi

  step "Installing backend dependencies"
  ensure_pip
  (
    cd "$ROOT_DIR"
    PIP_DISABLE_PIP_VERSION_CHECK=1 "$PYTHON_CMD" -m pip install -e .
  )
  ok "Backend dependencies installed."
}

frontend_dependencies_ready() {
  [[ -d "$FRONTEND_DIR/node_modules" ]] || return 1
  [[ -f "$FRONTEND_DIR/node_modules/.package-lock.json" ]] || return 1
  if [[ "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_DIR/node_modules/.package-lock.json" ]]; then
    return 1
  fi
  return 0
}

install_frontend_dependencies() {
  if frontend_dependencies_ready; then
    ok "Frontend dependencies are ready."
    return 0
  fi

  if ! is_truthy "$AUTO_INSTALL_FRONTEND_DEPS"; then
    die "Frontend dependencies are incomplete. Set AUTO_INSTALL_FRONTEND_DEPS=true or run 'cd $FRONTEND_DIR && npm ci'"
  fi

  step "Installing frontend dependencies"
  (
    cd "$FRONTEND_DIR"
    npm ci
  )
  ok "Frontend dependencies installed."
}

ensure_runtime_layout() {
  "$PYTHON_CMD" - <<'PY'
from tools import runtime_paths
runtime_paths.ensure_runtime_layout()
print(runtime_paths.get_runtime_dir())
PY
}

sqlite_path() {
  "$PYTHON_CMD" - <<'PY'
from config.db_config import sqlite_db_config
print(sqlite_db_config["db_path"])
PY
}

initialize_sqlite() {
  local sqlite_db
  if ! is_truthy "$AUTO_INIT_SQLITE"; then
    warn "Skipping SQLite initialization because AUTO_INIT_SQLITE=false."
    return 0
  fi

  step "Initializing SQLite storage"
  sqlite_db="$("$PYTHON_CMD" - <<'PY'
from database.sqlite_storage import get_sqlite_storage
status = get_sqlite_storage().initialize()
print(status["path"])
PY
)"
  info "SQLite database: $sqlite_db"
  ok "SQLite storage is ready."
}

build_frontend() {
  if is_truthy "$SKIP_FRONTEND_BUILD"; then
    warn "Skipping frontend build because SKIP_FRONTEND_BUILD=true."
    return 0
  fi

  step "Building frontend bundle"
  (
    cd "$FRONTEND_DIR"
    npm run build
  )
  ok "Frontend bundle published to runtime/webui."
}

port_pids() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "( sport = :$port )" 2>/dev/null \
      | grep -oE 'pid=[0-9]+' \
      | cut -d= -f2 \
      | sort -u || true
    return 0
  fi

  if command -v fuser >/dev/null 2>&1; then
    fuser "$port"/tcp 2>/dev/null | tr ' ' '\n' | awk 'NF' | sort -u || true
    return 0
  fi

  warn "No supported port inspection command found (lsof/ss/fuser). Port conflict detection is limited."
  return 0
}

is_same_project_backend() {
  local pid="$1"
  local command_line cwd root_real
  local tracked_pid tracked_pgid pid_pgid parent_pid depth

  command_line="$(ps -o command= -p "$pid" 2>/dev/null || true)"
  [[ -n "$command_line" ]] || return 1

  tracked_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$tracked_pid" ]] && kill -0 "$tracked_pid" >/dev/null 2>&1; then
    tracked_pgid="$(ps -o pgid= -p "$tracked_pid" 2>/dev/null | tr -d ' ' || true)"
    pid_pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$pid" == "$tracked_pid" ]]; then
      return 0
    fi
    if [[ -n "$tracked_pgid" && -n "$pid_pgid" && "$tracked_pgid" == "$pid_pgid" ]]; then
      return 0
    fi

    parent_pid="$pid"
    for (( depth = 0; depth < 8; depth++ )); do
      parent_pid="$(ps -o ppid= -p "$parent_pid" 2>/dev/null | tr -d ' ' || true)"
      [[ -n "$parent_pid" && "$parent_pid" != "0" ]] || break
      if [[ "$parent_pid" == "$tracked_pid" ]]; then
        return 0
      fi
    done
  fi

  if [[ "$command_line" != *"uvicorn"* && "$command_line" != *"apps.api.serve:app"* && "$command_line" != *"api.main"* ]]; then
    return 1
  fi

  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  root_real="$(readlink -f "$ROOT_DIR")"

  [[ "$command_line" == *"$root_real"* || "$cwd" == "$root_real" ]]
}

stop_pid() {
  local pid="$1"
  local grace_seconds="${2:-15}"
  local pgid

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
  if [[ -n "$pgid" && -n "$CURRENT_SHELL_PGID" && "$pgid" != "$CURRENT_SHELL_PGID" ]]; then
    kill -TERM -- "-$pgid" >/dev/null 2>&1 || true
  else
    kill -TERM "$pid" >/dev/null 2>&1 || true
  fi

  local waited=0
  while kill -0 "$pid" >/dev/null 2>&1; do
    if (( waited >= grace_seconds * 10 )); then
      break
    fi
    sleep 0.1
    waited=$((waited + 1))
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    if [[ -n "$pgid" && -n "$CURRENT_SHELL_PGID" && "$pgid" != "$CURRENT_SHELL_PGID" ]]; then
      kill -KILL -- "-$pgid" >/dev/null 2>&1 || true
    else
      kill -KILL "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

next_available_port() {
  local start_port="$1"
  local limit="$2"
  local candidate

  for (( candidate = start_port; candidate <= start_port + limit; candidate++ )); do
    if ! port_pids "$candidate" | grep -q .; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

select_api_port() {
  local requested_port="$1"
  local -a pids=()
  local -a same_project_pids=()
  local -a foreign_pids=()
  local next_port
  local pid

  mapfile -t pids < <(port_pids "$requested_port")
  if (( ${#pids[@]} == 0 )); then
    printf '%s\n' "$requested_port"
    return 0
  fi

  case "$PORT_CONFLICT_POLICY" in
    fail)
      die "Port $requested_port is already in use."
      ;;
    replace)
      warn "Port $requested_port is already in use. Replacing the existing listener because PORT_CONFLICT_POLICY=replace."
      for pid in "${pids[@]}"; do
        stop_pid "$pid" 15
      done
      printf '%s\n' "$requested_port"
      ;;
    increment)
      next_port="$(next_available_port "$((requested_port + 1))" "$API_PORT_SEARCH_LIMIT")" \
        || die "Could not find a free port after $requested_port."
      warn "Port $requested_port is busy. Switching to $next_port."
      printf '%s\n' "$next_port"
      ;;
    reuse)
      for pid in "${pids[@]}"; do
        if is_same_project_backend "$pid"; then
          same_project_pids+=("$pid")
        else
          foreign_pids+=("$pid")
        fi
      done
      if (( ${#foreign_pids[@]} > 0 )); then
        die "Port $requested_port is occupied by another service. Reuse is only supported for the same project backend."
      fi
      REUSED_BACKEND=1
      warn "Port $requested_port is already served by the same project backend. Reusing it."
      printf '%s\n' "$requested_port"
      ;;
    smart)
      for pid in "${pids[@]}"; do
        if is_same_project_backend "$pid"; then
          same_project_pids+=("$pid")
        else
          foreign_pids+=("$pid")
        fi
      done
      if (( ${#foreign_pids[@]} == 0 )); then
        warn "Port $requested_port is occupied by an older Social-Crawler backend. Replacing it."
        for pid in "${same_project_pids[@]}"; do
          stop_pid "$pid" 15
        done
        printf '%s\n' "$requested_port"
        return 0
      fi
      next_port="$(next_available_port "$((requested_port + 1))" "$API_PORT_SEARCH_LIMIT")" \
        || die "Port $requested_port is busy and no free port was found in the next $API_PORT_SEARCH_LIMIT ports."
      warn "Port $requested_port is occupied by another service. Switching to $next_port."
      printf '%s\n' "$next_port"
      ;;
    *)
      die "Unsupported PORT_CONFLICT_POLICY: $PORT_CONFLICT_POLICY"
      ;;
  esac
}

wait_for_health() {
  local port="$1"
  local timeout_seconds="$2"
  local started_at="$SECONDS"

  while (( SECONDS - started_at < timeout_seconds )); do
    if "$PYTHON_CMD" - "$port" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
    payload = json.load(response)
if payload.get("status") != "ok":
    raise SystemExit(1)
PY
    then
      return 0
    fi

    if [[ -n "$BACKEND_PID" ]] && ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      return 1
    fi
    sleep 1
  done

  return 1
}

run_env_check() {
  "$PYTHON_CMD" - "$1" <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/env/check", timeout=10) as response:
        payload = json.load(response)
except Exception as exc:
    print(f"warning:{exc}")
    raise SystemExit(0)

if payload.get("success"):
    print(f"ok:{payload.get('message', 'Environment check passed')}")
else:
    error_text = payload.get("error") or payload.get("message") or "Environment check failed"
    print(f"warning:{error_text}")
PY
}

print_recent_logs() {
  if [[ -f "$BACKEND_LOG_PATH" ]]; then
    warn "Recent backend log tail:"
    tail -n 80 "$BACKEND_LOG_PATH" >&2 || true
  fi
}

start_backend() {
  local -a command=(
    "$PYTHON_CMD" -m uvicorn apps.api.serve:app
    --app-dir "$ROOT_DIR"
    --host "$API_HOST"
    --port "$FINAL_API_PORT"
    --workers "$UVICORN_WORKERS"
    --proxy-headers
  )
  local -a extra_args=()

  if [[ -n "$UVICORN_EXTRA_ARGS" ]]; then
    read -r -a extra_args <<<"$UVICORN_EXTRA_ARGS"
    command+=("${extra_args[@]}")
  fi

  mkdir -p "$(dirname "$BACKEND_LOG_PATH")"
  : >"$BACKEND_LOG_PATH"

  step "Starting backend"
  info "Backend log: $BACKEND_LOG_PATH"

  if command -v setsid >/dev/null 2>&1; then
    (
      cd "$ROOT_DIR"
      exec setsid "${command[@]}" >>"$BACKEND_LOG_PATH" 2>&1
    ) &
  else
    (
      cd "$ROOT_DIR"
      exec "${command[@]}" >>"$BACKEND_LOG_PATH" 2>&1
    ) &
  fi

  BACKEND_PID=$!
  STARTED_BACKEND=1
  printf '%s\n' "$BACKEND_PID" >"$PID_FILE"
}

cleanup() {
  local exit_code="$?"
  trap - EXIT INT TERM

  if [[ "$STARTED_BACKEND" == "1" && -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    info "Stopping backend process group..."
    stop_pid "$BACKEND_PID" 10
  fi

  rm -f "$PID_FILE" >/dev/null 2>&1 || true
  exit "$exit_code"
}

print_banner() {
  cat <<EOF
============================================================
 Social-Crawler Production Startup
============================================================
 project root : $ROOT_DIR
 public host  : $PUBLIC_HOST_HINT
 api host     : $API_HOST
 api port req : $API_PORT
 started at   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')
============================================================
EOF
}

print_urls() {
  cat <<EOF

Welcome to Social-Crawler.

Frontend:
  http://$PUBLIC_HOST_HINT:$FINAL_API_PORT/
  http://127.0.0.1:$FINAL_API_PORT/

Backend API:
  http://$PUBLIC_HOST_HINT:$FINAL_API_PORT/api
  http://127.0.0.1:$FINAL_API_PORT/api

OpenAPI Docs:
  http://$PUBLIC_HOST_HINT:$FINAL_API_PORT/docs
  http://127.0.0.1:$FINAL_API_PORT/docs

Health Check:
  http://$PUBLIC_HOST_HINT:$FINAL_API_PORT/api/health

SQLite:
  $(sqlite_path)

Logs:
  $BACKEND_LOG_PATH
EOF
}

main() {
  local bootstrap_python python_version node_version npm_version runtime_dir env_check_result runtime_webui

  trap cleanup EXIT INT TERM
  print_banner

  step "Checking base runtime"
  load_nvm_if_needed
  require_command bash "This script must run under bash."
  require_command node "Install Node.js >= 18 first."
  require_command npm "Install npm together with Node.js."
  bootstrap_python="$(resolve_python)" || die "Python was not found. Install Python 3.11+ first."
  python_version="$(get_python_version "$bootstrap_python")"
  assert_python_version "$python_version"
  node_version="$(node -p 'process.versions.node')"
  npm_version="$(npm --version)"
  assert_node_version "$node_version"
  info "Python: $python_version ($bootstrap_python)"
  info "Node.js: $node_version"
  info "npm: $npm_version"

  step "Preparing environment files"
  ensure_env_file
  check_env_placeholders

  ensure_virtualenv "$bootstrap_python"
  PYTHON_CMD="$(resolve_python)" || die "Unable to resolve the project Python interpreter."
  python_version="$(get_python_version "$PYTHON_CMD")"
  assert_python_version "$python_version"
  ok "Project Python interpreter: $PYTHON_CMD"

  step "Preparing backend environment"
  install_backend_dependencies

  step "Preparing runtime directories"
  runtime_dir="$(ensure_runtime_layout)"
  ok "Runtime directory: $runtime_dir"

  initialize_sqlite

  step "Preparing frontend environment"
  install_frontend_dependencies
  build_frontend
  runtime_webui="$ROOT_DIR/runtime/webui/index.html"
  if [[ -f "$runtime_webui" ]]; then
    ok "Frontend entry found at $runtime_webui"
  else
    warn "runtime/webui/index.html was not found. The backend will fall back to api/webui if available."
  fi

  step "Resolving API port"
  FINAL_API_PORT="$(select_api_port "$API_PORT")"
  ok "API port: $FINAL_API_PORT"

  if [[ "$REUSED_BACKEND" == "1" ]]; then
    step "Checking reused backend health"
    if ! wait_for_health "$FINAL_API_PORT" "$STARTUP_TIMEOUT_SEC"; then
      die "The reused backend on port $FINAL_API_PORT did not pass health check."
    fi
  else
    start_backend
    if ! wait_for_health "$FINAL_API_PORT" "$STARTUP_TIMEOUT_SEC"; then
      print_recent_logs
      die "Backend failed to become healthy within ${STARTUP_TIMEOUT_SEC}s."
    fi
  fi

  step "Running API environment check"
  env_check_result="$(run_env_check "$FINAL_API_PORT")"
  case "$env_check_result" in
    ok:*)
      ok "${env_check_result#ok:}"
      ;;
    warning:*)
      warn "${env_check_result#warning:}"
      ;;
    *)
      warn "Unexpected /api/env/check output: $env_check_result"
      ;;
  esac

  print_urls

  if [[ "$REUSED_BACKEND" == "1" ]]; then
    info "Backend is being reused. Script will exit without stopping it."
    STARTED_BACKEND=0
    trap - EXIT INT TERM
    rm -f "$PID_FILE" >/dev/null 2>&1 || true
    exit 0
  fi

  info "Server is running. Press Ctrl+C to stop."
  wait "$BACKEND_PID"
}

main "$@"
