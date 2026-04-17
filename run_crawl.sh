#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "[Deprecated Entry] run_crawl.sh is kept for compatibility. Target layout: apps/crawler."

if [[ -n "${PYTHON_BIN:-}" ]]; then
  "$PYTHON_BIN" apps/crawler/run_tasks.py "$@"
  exit $?
fi

if [[ -x ".venv/bin/python" ]]; then
  .venv/bin/python apps/crawler/run_tasks.py "$@"
  exit $?
fi

if [[ -x ".venv/Scripts/python.exe" ]]; then
  .venv/Scripts/python.exe apps/crawler/run_tasks.py "$@"
  exit $?
fi

if command -v python3 >/dev/null 2>&1; then
  python3 apps/crawler/run_tasks.py "$@"
  exit $?
fi

if command -v python >/dev/null 2>&1; then
  python apps/crawler/run_tasks.py "$@"
  exit $?
fi

echo "Python interpreter not found. Please install Python 3.10+."
exit 1
