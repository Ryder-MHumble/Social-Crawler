#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  "$PYTHON_BIN" tasks/runner/run_crawl.py "$@"
  exit $?
fi

if [[ -x ".venv/bin/python" ]]; then
  .venv/bin/python tasks/runner/run_crawl.py "$@"
  exit $?
fi

if [[ -x ".venv/Scripts/python.exe" ]]; then
  .venv/Scripts/python.exe tasks/runner/run_crawl.py "$@"
  exit $?
fi

if command -v python3 >/dev/null 2>&1; then
  python3 tasks/runner/run_crawl.py "$@"
  exit $?
fi

if command -v python >/dev/null 2>&1; then
  python tasks/runner/run_crawl.py "$@"
  exit $?
fi

echo "Python interpreter not found. Please install Python 3.10+."
exit 1

