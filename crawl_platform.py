#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Single platform crawler script
Used for parallel crawling of multiple platforms

Usage:
    python crawl_platform.py xhs
    python crawl_platform.py dy
"""

import subprocess
import sys
from pathlib import Path

# Keywords to search (comma-separated)
KEYWORDS = "中关村人工智能研究院,北京中关村学院"

# Common settings
LOGIN_TYPE = "qrcode"  # Use QR code login
CRAWLER_TYPE = "search"  # Search mode
SAVE_DATA_OPTION = "json"  # Save as JSON files
ENABLE_COMMENTS = "yes"  # Crawl comments


def run_crawler(platform: str):
    """
    Run the crawler for a specific platform

    Args:
        platform: Platform name (xhs, dy, bili, wb, etc.)
    """
    platform_names = {
        "xhs": "小红书",
        "dy": "抖音",
        "bili": "Bilibili",
        "wb": "微博",
        "ks": "快手",
        "tieba": "贴吧",
        "zhihu": "知乎"
    }

    print(f"\n{'='*60}")
    print(f"[{platform.upper()}] 开始爬取 {platform_names.get(platform, platform)}")
    print(f"[{platform.upper()}] 关键词: {KEYWORDS}")
    print(f"{'='*60}\n")

    # Build command
    cmd = [
        "uv", "run", "main.py",
        "--platform", platform,
        "--lt", LOGIN_TYPE,
        "--type", CRAWLER_TYPE,
        "--keywords", KEYWORDS,
        "--save_data_option", SAVE_DATA_OPTION,
        "--get_comment", ENABLE_COMMENTS,
    ]

    try:
        # Run the command
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            cwd=Path(__file__).parent
        )

        print(f"\n✅ [{platform.upper()}] {platform_names.get(platform, platform)} 爬取完成！")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ [{platform.upper()}] {platform_names.get(platform, platform)} 爬取失败！")
        print(f"错误信息: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  [{platform.upper()}] 用户中断了爬取")
        return False


def main():
    """
    Main function
    """
    if len(sys.argv) < 2:
        print("使用方法: python crawl_platform.py <platform>")
        print("可选平台: xhs, dy, bili, wb, ks, tieba, zhihu")
        sys.exit(1)

    platform = sys.argv[1].lower()
    success = run_crawler(platform)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        sys.exit(1)
