#!/usr/bin/env python3
"""Backward-compatible wrapper for the Vibe Coding CLI."""

from __future__ import annotations

import asyncio

from vibe_coding.cli import main


if __name__ == "__main__":
    print("[Deprecated Entry] run_vibe_coding.py is kept for compatibility. Target layout: apps/crawler.")
    asyncio.run(main())
