#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"
echo "[Deprecated Entry] scripts/compat/run_crawl.sh -> use ./social_crawler.sh task ..."

exec ./social_crawler.sh task "$@"
