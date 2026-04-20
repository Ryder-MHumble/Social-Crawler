#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "[Deprecated Entry] run_crawl.sh -> use ./social_crawler.sh task ..."

exec ./social_crawler.sh task "$@"
