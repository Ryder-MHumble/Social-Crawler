#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Data Crawler

Dedicated crawler for collecting vibe coding related content from social media platforms.
This crawler focuses on AI-assisted coding, no-code tools, and indie hacking discussions.

Usage:
    python run_vibe_coding.py                    # Crawl all configured platforms
    python run_vibe_coding.py --platform xhs     # Crawl specific platform
    python run_vibe_coding.py --analyze          # Run AI analysis on pending content
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from config.vibe_coding_config import generate_crawl_session_id
from database.vibe_coding_store import VibeCodingStore
from tools import utils


async def crawl_platform_vibe_coding(platform: str):
    """
    Crawl a single platform for vibe coding content.

    Args:
        platform: Platform code (xhs, bili, dy, wb)
    """
    utils.logger.info(f"\n{'='*60}")
    utils.logger.info(f"Starting Vibe Coding Crawl: {platform.upper()}")
    utils.logger.info(f"Session ID: {config.CURRENT_CRAWL_SESSION_ID}")
    utils.logger.info(f"{'='*60}\n")

    # Temporarily override config for vibe coding keywords
    original_keywords = config.KEYWORDS
    vibe_keywords = getattr(config, "VIBE_CODING_KEYWORDS", [])
    config.KEYWORDS = ",".join(vibe_keywords[:10])  # Use first 10 keywords to avoid too many searches

    # Disable relevance filter (we have our own keyword matching in VibeCodingStore)
    original_relevance_filter = config.ENABLE_RELEVANCE_FILTER
    config.ENABLE_RELEVANCE_FILTER = False

    # Set higher engagement threshold
    original_min_engagement = config.MIN_CONTENT_ENGAGEMENT
    config.MIN_CONTENT_ENGAGEMENT = 0  # Let VibeCodingStore handle filtering

    # Reduce crawl count per keyword (vibe coding is more targeted)
    original_max_notes = config.CRAWLER_MAX_NOTES_COUNT
    config.CRAWLER_MAX_NOTES_COUNT = 20

    try:
        # Import platform-specific crawler
        if platform == "xhs":
            from media_platform.xhs import XiaoHongShuCrawler
            crawler = XiaoHongShuCrawler()
        elif platform == "bili":
            from media_platform.bilibili import BilibiliCrawler
            crawler = BilibiliCrawler()
        elif platform == "dy":
            from media_platform.douyin import DouYinCrawler
            crawler = DouYinCrawler()
        elif platform == "wb":
            from media_platform.weibo import WeiboCrawler
            crawler = WeiboCrawler()
        else:
            utils.logger.error(f"Unsupported platform: {platform}")
            return

        utils.logger.info(f"Crawling with keywords: {config.KEYWORDS}")

        # Start crawling (no init_config needed)
        await crawler.start()

        utils.logger.info(f"\n✅ {platform.upper()} vibe coding crawl completed!")

    except Exception as e:
        utils.logger.error(f"❌ {platform.upper()} crawl failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        # Restore original config
        config.KEYWORDS = original_keywords
        config.ENABLE_RELEVANCE_FILTER = original_relevance_filter
        config.MIN_CONTENT_ENGAGEMENT = original_min_engagement
        config.CRAWLER_MAX_NOTES_COUNT = original_max_notes


async def analyze_pending_content():
    """
    Run AI analysis on pending vibe coding content.
    This is a placeholder for future AI analysis pipeline.
    """
    utils.logger.info("\n" + "="*60)
    utils.logger.info("AI Analysis Pipeline")
    utils.logger.info("="*60 + "\n")

    if not config.ENABLE_VIBE_CODING_AI_ANALYSIS:
        utils.logger.warning("⚠️  AI analysis is disabled in config.")
        utils.logger.info("Set ENABLE_VIBE_CODING_AI_ANALYSIS = True to enable.")
        return

    # Fetch pending content
    utils.logger.info("Fetching pending content...")
    pending = VibeCodingStore.get_pending_analysis_content(limit=100)

    if not pending:
        utils.logger.info("✅ No pending content to analyze.")
        return

    utils.logger.info(f"Found {len(pending)} items pending analysis.")

    # TODO: Implement AI analysis pipeline
    # This would:
    # 1. Use Claude API to analyze each content item
    # 2. Extract innovation score, ideas, and categorization
    # 3. Update database with results
    # 4. Generate design proposals for high-scoring items

    utils.logger.warning("⚠️  AI analysis pipeline not yet implemented.")
    utils.logger.info("This will be integrated with OpenClaw in the next phase.")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Vibe Coding Data Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_vibe_coding.py                    # Crawl all platforms
  python run_vibe_coding.py --platform xhs     # Crawl XHS only
  python run_vibe_coding.py --analyze          # Run AI analysis
        """
    )

    parser.add_argument(
        "--platform",
        type=str,
        choices=["xhs", "bili", "dy", "wb"],
        help="Specific platform to crawl (default: all configured platforms)"
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run AI analysis on pending content instead of crawling"
    )

    args = parser.parse_args()

    # Check if vibe coding collection is enabled
    if not config.ENABLE_VIBE_CODING_COLLECTION:
        utils.logger.error("❌ Vibe coding collection is disabled in config.")
        utils.logger.info("Set ENABLE_VIBE_CODING_COLLECTION = True in config/vibe_coding_config.py")
        sys.exit(1)

    # Generate session ID for this crawl
    config.CURRENT_CRAWL_SESSION_ID = generate_crawl_session_id()

    try:
        if args.analyze:
            # Run AI analysis
            await analyze_pending_content()
        else:
            # Run crawler
            platforms = [args.platform] if args.platform else config.VIBE_CODING_PLATFORMS

            utils.logger.info("\n" + "="*60)
            utils.logger.info("🚀 Vibe Coding Data Collection")
            utils.logger.info("="*60)
            utils.logger.info(f"Platforms: {', '.join(platforms)}")
            utils.logger.info(f"Keywords: {len(config.VIBE_CODING_KEYWORDS)} configured")
            utils.logger.info(f"Session: {config.CURRENT_CRAWL_SESSION_ID}")
            utils.logger.info("="*60 + "\n")

            for platform in platforms:
                await crawl_platform_vibe_coding(platform)

            utils.logger.info("\n" + "="*60)
            utils.logger.info("✅ All platforms completed!")
            utils.logger.info("="*60)

    except KeyboardInterrupt:
        utils.logger.warning("\n⚠️  Crawl interrupted by user.")
        sys.exit(0)
    except Exception as e:
        utils.logger.error(f"\n❌ Crawl failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
