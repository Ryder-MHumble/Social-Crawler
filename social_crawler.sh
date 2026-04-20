#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_DIR="$ROOT_DIR/scripts/launcher"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Social-Crawler 统一入口 (Linux/macOS)

直接运行:
  ./social_crawler.sh
  ./social_crawler.sh menu
  ./social_crawler.sh help

开发环境:
  ./social_crawler.sh dev start
  ./social_crawler.sh dev stop
  ./social_crawler.sh dev status
  ./social_crawler.sh dev logs -f

生产环境:
  ./social_crawler.sh prod start
  ./social_crawler.sh prod stop
  ./social_crawler.sh prod status
  ./social_crawler.sh prod logs -f

任务执行:
  ./social_crawler.sh task --list
  ./social_crawler.sh task sentiment_monitor

说明:
  - 不带参数时会打印帮助；在交互终端中会进入菜单
  - dev/prod 真实实现已收拢到 scripts/launcher/
  - 根目录对外只保留这一个 shell 入口
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
  SOCIAL_CRAWLER_CMD_HINT="${SOCIAL_CRAWLER_CMD_HINT:-./social_crawler.sh}" \
    "$LAUNCHER_DIR/dev.sh" "$@"
}

run_prod() {
  SOCIAL_CRAWLER_CMD_HINT="${SOCIAL_CRAWLER_CMD_HINT:-./social_crawler.sh}" \
    "$LAUNCHER_DIR/prod.sh" "$@"
}

menu() {
  while true; do
    cat <<'EOF'

请选择操作:
  1) 开发环境启动
  2) 开发环境关闭
  3) 开发环境日志
  4) 生产环境启动
  5) 生产环境关闭
  6) 生产环境日志
  7) 查看任务列表
  8) 自定义任务参数
  9) 查看帮助
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
      *) echo "未知选项: $choice" ;;
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
    echo "未知操作: $ACTION"
    usage
    exit 1
    ;;
esac
