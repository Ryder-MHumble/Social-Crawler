#!/usr/bin/env python3
"""Compatibility entrypoint for unified crawler tasks."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasks.runner.run_crawl import main


if __name__ == "__main__":
    raise SystemExit(main())
