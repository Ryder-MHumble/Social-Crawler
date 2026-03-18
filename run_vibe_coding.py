#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Crawler — Entry Point
===================================
Collects AI-coding / vibe-coding content from social media platforms
and saves it to the vibe_coding_raw_data Supabase table.

Usage
-----
  python run_vibe_coding.py                         # crawl all platforms
  python run_vibe_coding.py --platform xhs          # single platform
  python run_vibe_coding.py --platform xhs bili     # multiple platforms
  python run_vibe_coding.py --list-keywords         # show configured keywords

OpenClaw call
-------------
  {
    "command": "python run_vibe_coding.py",
    "cwd": "<MediaCrawler root>"
  }
"""

import argparse
import asyncio
import sys

# ---------------------------------------------------------------------------
# Bootstrap: make sure project root is on sys.path when called from anywhere
# ---------------------------------------------------------------------------
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import vibe_coding.config as vc_cfg
from vibe_coding.config import generate_crawl_session_id
from vibe_coding.crawler import crawl_all
from tools import utils


def _list_keywords():
    print("\n=== Tier A (score 4 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_A:
        print(f"  {kw}")
    print("\n=== Tier B (score 2 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_B:
        print(f"  {kw}")
    print("\n=== Tier C (score 1 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_C:
        print(f"  {kw}")
    print(f"\n=== Blacklist ===")
    for kw in vc_cfg.KEYWORDS_BLACKLIST:
        print(f"  {kw}")
    print(f"\nScore threshold: {vc_cfg.KEYWORD_SCORE_THRESHOLD}")
    print(f"Search keywords ({len(vc_cfg.SEARCH_KEYWORDS)}): {vc_cfg.SEARCH_KEYWORDS}")
    print()


async def main():
    parser = argparse.ArgumentParser(
        description="Vibe Coding Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=["xhs", "bili", "dy", "wb"],
        metavar="PLATFORM",
        help="Platforms to crawl (default: all in config). Choices: xhs bili dy wb",
    )
    parser.add_argument(
        "--list-keywords",
        action="store_true",
        help="Print keyword tiers and exit",
    )
    args = parser.parse_args()

    if args.list_keywords:
        _list_keywords()
        return

    if not vc_cfg.ENABLE_VIBE_CODING_COLLECTION:
        utils.logger.error(
            "ENABLE_VIBE_CODING_COLLECTION is False — set it to True in vibe_coding/config.py"
        )
        sys.exit(1)

    # Set session ID for batch tracking
    vc_cfg.CURRENT_CRAWL_SESSION_ID = generate_crawl_session_id()

    platforms = args.platform or vc_cfg.VIBE_CODING_PLATFORMS

    utils.logger.info("=" * 56)
    utils.logger.info("Vibe Coding Data Collection")
    utils.logger.info(f"  Session : {vc_cfg.CURRENT_CRAWL_SESSION_ID}")
    utils.logger.info(f"  Platforms: {', '.join(platforms)}")
    utils.logger.info(f"  Keywords : {len(vc_cfg.SEARCH_KEYWORDS)} search queries")
    utils.logger.info(f"  Threshold: score >= {vc_cfg.KEYWORD_SCORE_THRESHOLD}")
    utils.logger.info(f"  Min eng  : {vc_cfg.VIBE_CODING_MIN_ENGAGEMENT}")
    utils.logger.info("=" * 56)

    try:
        await crawl_all(platforms)
    except KeyboardInterrupt:
        utils.logger.warning("Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        utils.logger.error(f"Crawl failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
