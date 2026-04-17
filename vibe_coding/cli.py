#!/usr/bin/env python3
"""Vibe Coding crawler entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys

import vibe_coding.config as vc_cfg
from tools import utils
from vibe_coding.config import generate_crawl_session_id
from vibe_coding.crawler import crawl_all


def _list_keywords() -> None:
    print("\n=== Tier A (score 4 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_A:
        print(f"  {kw}")
    print("\n=== Tier B (score 2 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_B:
        print(f"  {kw}")
    print("\n=== Tier C (score 1 each) ===")
    for kw in vc_cfg.KEYWORDS_TIER_C:
        print(f"  {kw}")
    print("\n=== Blacklist ===")
    for kw in vc_cfg.KEYWORDS_BLACKLIST:
        print(f"  {kw}")
    print(f"\nScore threshold: {vc_cfg.KEYWORD_SCORE_THRESHOLD}")
    print(f"Search keywords ({len(vc_cfg.SEARCH_KEYWORDS)}): {vc_cfg.SEARCH_KEYWORDS}")
    print()


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vibe Coding crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=["xhs", "bili", "dy", "wb"],
        metavar="PLATFORM",
        help="Platforms to crawl (default: all in config).",
    )
    parser.add_argument(
        "--list-keywords",
        action="store_true",
        help="Print keyword tiers and exit.",
    )
    parser.add_argument(
        "--search-keywords",
        help="Comma-separated search keywords to override config.",
    )
    parser.add_argument(
        "--max-notes-per-keyword",
        type=int,
        help="Override max search results per keyword.",
    )
    parser.add_argument(
        "--min-engagement",
        type=int,
        help="Override minimum engagement threshold.",
    )
    parser.add_argument(
        "--enabled",
        help="Override ENABLE_VIBE_CODING_COLLECTION with true/false.",
    )
    args = parser.parse_args()

    if args.list_keywords:
        _list_keywords()
        return

    if args.enabled is not None:
        vc_cfg.ENABLE_VIBE_CODING_COLLECTION = _parse_bool(args.enabled)
    if args.search_keywords:
        vc_cfg.SEARCH_KEYWORDS = [
            item.strip() for item in args.search_keywords.split(",") if item.strip()
        ]
    if args.max_notes_per_keyword is not None:
        vc_cfg.VIBE_CODING_MAX_NOTES_PER_KEYWORD = max(1, args.max_notes_per_keyword)
    if args.min_engagement is not None:
        vc_cfg.VIBE_CODING_MIN_ENGAGEMENT = max(0, args.min_engagement)

    if not vc_cfg.ENABLE_VIBE_CODING_COLLECTION:
        utils.logger.error(
            "ENABLE_VIBE_CODING_COLLECTION is False - set it to True in vibe_coding/config.py"
        )
        sys.exit(1)

    vc_cfg.CURRENT_CRAWL_SESSION_ID = generate_crawl_session_id()
    platforms = args.platform or vc_cfg.VIBE_CODING_PLATFORMS

    utils.logger.info("=" * 56)
    utils.logger.info("Vibe Coding Data Collection")
    utils.logger.info(f"  Session : {vc_cfg.CURRENT_CRAWL_SESSION_ID}")
    utils.logger.info(f"  Platforms: {', '.join(platforms)}")
    utils.logger.info(f"  Keywords : {len(vc_cfg.SEARCH_KEYWORDS)} search queries")
    utils.logger.info(f"  Threshold: score >= {vc_cfg.KEYWORD_SCORE_THRESHOLD}")
    utils.logger.info(f"  Min eng  : {vc_cfg.VIBE_CODING_MIN_ENGAGEMENT}")
    utils.logger.info(
        f"  Max notes: {vc_cfg.VIBE_CODING_MAX_NOTES_PER_KEYWORD} per keyword"
    )
    utils.logger.info("=" * 56)

    try:
        await crawl_all(platforms)
    except KeyboardInterrupt:
        utils.logger.warning("Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        utils.logger.error(f"Crawl failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
