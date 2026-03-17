#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor vibe coding crawl progress in real-time.
"""

import sys
from pathlib import Path
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.supabase_client import get_supabase
from tools import utils

def get_stats():
    """Get current statistics from vibe_coding_raw_data table."""
    try:
        sb = get_supabase()

        # Total count
        total_result = sb.table("vibe_coding_raw_data").select("id", count="exact").execute()
        total_count = total_result.count or 0

        # Count by platform
        platform_result = sb.table("vibe_coding_raw_data").select("platform", count="exact").execute()
        platforms = {}
        for row in platform_result.data:
            platform = row.get("platform", "unknown")
            platforms[platform] = platforms.get(platform, 0) + 1

        # Count by trend category
        category_result = sb.table("vibe_coding_raw_data").select("trend_category", count="exact").execute()
        categories = {}
        for row in category_result.data:
            category = row.get("trend_category", "unknown")
            categories[category] = categories.get(category, 0) + 1

        # Latest items
        latest_result = sb.table("vibe_coding_raw_data").select(
            "platform,title,vibe_coding_keywords,trend_category,liked_count,comment_count"
        ).order("created_at", desc=True).limit(5).execute()

        return {
            "total": total_count,
            "platforms": platforms,
            "categories": categories,
            "latest": latest_result.data or []
        }

    except Exception as e:
        utils.logger.error(f"Failed to get stats: {e}")
        return None

def display_stats(stats):
    """Display statistics in a nice format."""
    if not stats:
        print("❌ Failed to fetch statistics")
        return

    print("\n" + "="*60)
    print("📊 Vibe Coding Data Collection Statistics")
    print("="*60)

    print(f"\n📦 Total Items: {stats['total']}")

    if stats['platforms']:
        print("\n🌐 By Platform:")
        for platform, count in sorted(stats['platforms'].items(), key=lambda x: x[1], reverse=True):
            platform_names = {"xhs": "小红书", "bili": "B站", "dy": "抖音", "wb": "微博"}
            name = platform_names.get(platform, platform.upper())
            print(f"   {name}: {count}")

    if stats['categories']:
        print("\n📂 By Category:")
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            print(f"   {category}: {count}")

    if stats['latest']:
        print("\n🆕 Latest 5 Items:")
        for i, item in enumerate(stats['latest'], 1):
            title = item.get('title', 'No title')[:40]
            keywords = item.get('vibe_coding_keywords', [])
            category = item.get('trend_category', 'unknown')
            likes = item.get('liked_count', 0)
            comments = item.get('comment_count', 0)
            print(f"\n   {i}. {title}...")
            print(f"      Category: {category}")
            print(f"      Keywords: {', '.join(keywords[:3])}")
            print(f"      Engagement: {likes}👍 {comments}💬")

    print("\n" + "="*60)

def monitor_loop(interval=10):
    """Monitor in a loop."""
    print("🔄 Monitoring vibe coding data collection...")
    print(f"   Refreshing every {interval} seconds (Ctrl+C to stop)")

    try:
        while True:
            stats = get_stats()
            display_stats(stats)
            print(f"\n⏰ Next update in {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor vibe coding crawl progress")
    parser.add_argument("--once", action="store_true", help="Show stats once and exit")
    parser.add_argument("--interval", type=int, default=10, help="Refresh interval in seconds (default: 10)")

    args = parser.parse_args()

    if args.once:
        stats = get_stats()
        display_stats(stats)
    else:
        monitor_loop(args.interval)
