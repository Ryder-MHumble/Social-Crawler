#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Automated crawler script for XiaoHongShu (小红书) and Douyin (抖音)
Searches for specific keywords and saves the results

Usage:
    python auto_crawl.py
    or
    uv run auto_crawl.py
"""

import subprocess
import sys
from pathlib import Path

# Keywords to search (comma-separated)
KEYWORDS = "中关村人工智能研究院,北京中关村学院"

# Platforms to crawl
PLATFORMS = ["xhs", "dy", "bili", "wb"]  # xhs = 小红书, dy = 抖音

# Common settings
LOGIN_TYPE = "qrcode"  # Use QR code login
CRAWLER_TYPE = "search"  # Search mode
SAVE_DATA_OPTION = "json"  # Save as JSON files
MAX_NOTES_COUNT = 10  # Number of posts to crawl per keyword (can be adjusted)
ENABLE_COMMENTS = "yes"  # Crawl comments


def run_crawler(platform: str):
    """
    Run the crawler for a specific platform

    Args:
        platform: Platform name (xhs or dy)
    """
    platform_names = {
        "xhs": "小红书",
        "dy": "抖音",
        "bili": "bilibili",
        "wb": "微博"
    }

    print(f"\n{'='*60}")
    print(f"开始爬取 {platform_names.get(platform, platform)}")
    print(f"关键词: {KEYWORDS}")
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

        print(f"\n✅ {platform_names.get(platform, platform)} 爬取完成！")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ {platform_names.get(platform, platform)} 爬取失败！")
        print(f"错误信息: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断了 {platform_names.get(platform, platform)} 的爬取")
        return False


def main():
    """
    Main function to run crawlers for all platforms
    """
    print("\n" + "="*60)
    print("自动化爬虫脚本启动")
    print("="*60)
    print(f"目标关键词: {KEYWORDS}")
    print(f"爬取平台: {', '.join([p.upper() for p in PLATFORMS])}")
    print(f"登录方式: QR Code 扫码登录")
    print(f"数据保存格式: {SAVE_DATA_OPTION.upper()}")
    print("="*60 + "\n")

    print("⚠️  注意事项:")
    print("1. 第一次运行需要扫码登录，登录状态会自动保存")
    print("2. 后续运行会自动使用已保存的登录状态")
    print("3. 如果扫码登录界面出现，请使用对应 APP 扫码")
    print("4. 数据将保存在 data/ 目录下\n")

    success_count = 0
    failed_platforms = []

    for platform in PLATFORMS:
        success = run_crawler(platform)
        if success:
            success_count += 1
        else:
            failed_platforms.append(platform)

    # Summary
    print("\n" + "="*60)
    print("爬取任务完成总结")
    print("="*60)
    print(f"✅ 成功: {success_count}/{len(PLATFORMS)} 个平台")

    if failed_platforms:
        print(f"❌ 失败: {', '.join(failed_platforms)}")

    print("\n💾 数据保存位置: data/ 目录")
    print("="*60 + "\n")

    return 0 if success_count == len(PLATFORMS) else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        sys.exit(1)
