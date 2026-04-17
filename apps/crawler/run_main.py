#!/usr/bin/env python3
"""Compatibility entrypoint for single-platform crawler main.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import runtime_paths


if __name__ == "__main__":
    runpy.run_path(str(runtime_paths.get_repo_path("main.py")), run_name="__main__")
