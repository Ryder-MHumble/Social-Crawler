# -*- coding: utf-8 -*-
"""
Vibe Coding Crawler Orchestration

Patches global config temporarily, then runs platform crawlers.
Called by run_vibe_coding.py (project root).
"""

import asyncio
from typing import List, Optional

import config as global_cfg
import vibe_coding.config as vc_cfg
from tools import utils


async def crawl_platform(platform: str):
    """Run vibe coding crawl for a single platform."""
    utils.logger.info(f"\n{'='*56}")
    utils.logger.info(f"[VibeCoding] Platform: {platform.upper()}  Session: {vc_cfg.CURRENT_CRAWL_SESSION_ID}")
    utils.logger.info(f"{'='*56}")

    # Patch global config for this run
    _orig = {
        "KEYWORDS": global_cfg.KEYWORDS,
        "ENABLE_RELEVANCE_FILTER": global_cfg.ENABLE_RELEVANCE_FILTER,
        "MIN_CONTENT_ENGAGEMENT": global_cfg.MIN_CONTENT_ENGAGEMENT,
        "CRAWLER_MAX_NOTES_COUNT": global_cfg.CRAWLER_MAX_NOTES_COUNT,
    }

    # Use our curated search keywords; rotate through all of them
    global_cfg.KEYWORDS = ",".join(vc_cfg.SEARCH_KEYWORDS)
    global_cfg.ENABLE_RELEVANCE_FILTER = False          # VibeCodingStore handles its own filtering
    global_cfg.MIN_CONTENT_ENGAGEMENT = 0               # same — let store decide
    global_cfg.CRAWLER_MAX_NOTES_COUNT = vc_cfg.VIBE_CODING_MAX_NOTES_PER_KEYWORD

    try:
        crawler = _build_crawler(platform)
        if crawler is None:
            return
        utils.logger.info(f"[VibeCoding] Search keywords ({len(vc_cfg.SEARCH_KEYWORDS)}): {vc_cfg.SEARCH_KEYWORDS[:4]} ...")
        await crawler.start()
        utils.logger.info(f"[VibeCoding] {platform.upper()} done ✓")
    except Exception as e:
        utils.logger.error(f"[VibeCoding] {platform.upper()} failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        for k, v in _orig.items():
            setattr(global_cfg, k, v)


def _build_crawler(platform: str):
    if platform == "xhs":
        from media_platform.xhs import XiaoHongShuCrawler
        return XiaoHongShuCrawler()
    elif platform == "bili":
        from media_platform.bilibili import BilibiliCrawler
        return BilibiliCrawler()
    elif platform == "dy":
        from media_platform.douyin import DouYinCrawler
        return DouYinCrawler()
    elif platform == "wb":
        from media_platform.weibo import WeiboCrawler
        return WeiboCrawler()
    else:
        utils.logger.error(f"[VibeCoding] Unknown platform: {platform}")
        return None


async def crawl_all(platforms: Optional[List[str]] = None):
    targets = platforms or vc_cfg.VIBE_CODING_PLATFORMS
    utils.logger.info(f"\n[VibeCoding] Starting collection — platforms: {targets}")
    for p in targets:
        await crawl_platform(p)
    utils.logger.info("[VibeCoding] All platforms completed ✓\n")
