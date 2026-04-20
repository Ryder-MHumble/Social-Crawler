#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Social-Crawler Unified Launcher (Linux/macOS)

Usage:
  ./social_crawler.sh dev <start|stop|restart|status|logs> [--attach|-f]
  ./social_crawler.sh prod <start|stop|restart|status|logs> [--attach|-f]
  ./social_crawler.sh task [run_tasks.py args...]
  ./social_crawler.sh menu
  ./social_crawler.sh help

Examples:
  ./social_crawler.sh dev start
  ./social_crawler.sh dev logs -f
  ./social_crawler.sh prod restart
  ./social_crawler.sh prod logs -f
  ./social_crawler.sh task --list
  ./social_crawler.sh task sentiment_monitor
EOF
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

run_task() {
  local py
  py="$(resolve_python)" || {
    echo "Python interpreter not found. Please install Python 3.11+."
    exit 1
  }
  "$py" apps/crawler/run_tasks.py "$@"
}

run_dev() {
  ./start_dev_local.sh "$@"
}

run_prod() {
  ./start_prod_server.sh "$@"
}

menu() {
  while true; do
    cat <<'EOF'

Choose an action:
  1) dev start
  2) dev stop
  3) dev logs -f
  4) prod start
  5) prod stop
  6) prod logs -f
  7) task --list
  8) task (custom args)
  9) help
  0) exit
EOF
    read -r -p "> " choice
    case "$choice" in
      1) run_dev start ;;
      2) run_dev stop ;;
      3) run_dev logs -f ;;
      4) run_prod start ;;
      5) run_prod stop ;;
      6) run_prod logs -f ;;
      7) run_task --list ;;
      8)
        read -r -p "run_tasks args: " task_args
        # shellcheck disable=SC2086
        run_task $task_args
        ;;
      9) usage ;;
      0) exit 0 ;;
      *) echo "Unknown choice: $choice" ;;
    esac
  done
}

if [[ $# -eq 0 ]]; then
  usage
  if [[ -t 0 ]]; then
    menu
  fi
  exit 0
fi

ACTION="$1"
shift || true

case "$ACTION" in
  dev)
    if [[ $# -eq 0 ]]; then
      usage
      exit 1
    fi
    run_dev "$@"
    ;;
  prod)
    if [[ $# -eq 0 ]]; then
      usage
      exit 1
    fi
    run_prod "$@"
    ;;
  task)
    run_task "$@"
    ;;
  menu)
    menu
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown action: $ACTION"
    usage
    exit 1
    ;;
esac
