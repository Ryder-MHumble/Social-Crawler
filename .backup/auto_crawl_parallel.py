#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parallel automated crawler script for multiple platforms
Runs all platform crawlers simultaneously

Usage:
    python auto_crawl_parallel.py
    or
    uv run auto_crawl_parallel.py
"""

import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Keywords to search (comma-separated)
KEYWORDS = "中关村人工智能研究院,北京中关村学院"

# Platforms to crawl (will run in parallel)
PLATFORMS = ["xhs", "dy", "bili", "wb"]  # xhs = 小红书, dy = 抖音, bili = B站, wb = 微博

# Common settings
LOGIN_TYPE = "qrcode"  # Use QR code login
CRAWLER_TYPE = "search"  # Search mode
SAVE_DATA_OPTION = "json"  # Save as JSON files
ENABLE_COMMENTS = "yes"  # Crawl comments


def run_single_platform(platform: str):
    """
    Run the crawler for a single platform

    Args:
        platform: Platform name (xhs, dy, bili, wb, etc.)

    Returns:
        tuple: (platform, success, duration)
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

    print(f"\n🚀 [{platform.upper()}] 开始爬取 {platform_names.get(platform, platform)}...")

    start_time = time.time()

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
        # Run the command with output redirection
        log_file = Path(__file__).parent / f"logs/{platform}_crawl.log"
        log_file.parent.mkdir(exist_ok=True)

        with open(log_file, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=Path(__file__).parent
            )

        duration = time.time() - start_time
        success = result.returncode == 0

        if success:
            print(f"✅ [{platform.upper()}] {platform_names.get(platform, platform)} 爬取完成！耗时: {duration:.1f}秒")
        else:
            print(f"❌ [{platform.upper()}] {platform_names.get(platform, platform)} 爬取失败！查看日志: {log_file}")

        return (platform, success, duration)

    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ [{platform.upper()}] {platform_names.get(platform, platform)} 爬取异常: {e}")
        return (platform, False, duration)


def main():
    """
    Main function to run all crawlers in parallel
    """
    print("\n" + "="*70)
    print("🚀 并行自动化爬虫脚本启动")
    print("="*70)
    print(f"目标关键词: {KEYWORDS}")
    print(f"爬取平台: {', '.join([p.upper() for p in PLATFORMS])}")
    print(f"并行数量: {len(PLATFORMS)} 个平台同时运行")
    print(f"登录方式: QR Code 扫码登录")
    print(f"数据保存格式: {SAVE_DATA_OPTION.upper()}")
    print("="*70 + "\n")

    print("⚠️  注意事项:")
    print("1. 第一次运行需要分别为每个平台扫码登录")
    print("2. 建议先运行串行脚本完成首次登录，然后再使用并行脚本")
    print("3. 所有平台将同时开始爬取，请确保系统资源充足")
    print("4. 每个平台的日志会保存在 logs/ 目录下")
    print("5. 数据将保存在 data/ 目录下\n")

    # Ask for confirmation
    response = input("是否继续? (y/n): ").strip().lower()
    if response not in ['y', 'yes']:
        print("已取消执行")
        sys.exit(0)

    print("\n" + "="*70)
    print("开始并行爬取...")
    print("="*70 + "\n")

    start_time = time.time()
    results = []

    # Use ThreadPoolExecutor to run crawlers in parallel
    with ThreadPoolExecutor(max_workers=len(PLATFORMS)) as executor:
        # Submit all tasks
        future_to_platform = {
            executor.submit(run_single_platform, platform): platform
            for platform in PLATFORMS
        }

        # Collect results as they complete
        for future in as_completed(future_to_platform):
            platform = future_to_platform[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"❌ [{platform.upper()}] 执行异常: {e}")
                results.append((platform, False, 0))

    total_duration = time.time() - start_time

    # Summary
    print("\n" + "="*70)
    print("📊 爬取任务完成总结")
    print("="*70)

    success_count = sum(1 for _, success, _ in results if success)
    platform_names = {
        "xhs": "小红书",
        "dy": "抖音",
        "bili": "Bilibili",
        "wb": "微博",
        "ks": "快手",
        "tieba": "贴吧",
        "zhihu": "知乎"
    }

    print(f"\n总体统计:")
    print(f"  ✅ 成功: {success_count}/{len(PLATFORMS)} 个平台")
    print(f"  ⏱️  总耗时: {total_duration:.1f} 秒")

    print(f"\n详细结果:")
    for platform, success, duration in sorted(results, key=lambda x: x[0]):
        status = "✅ 成功" if success else "❌ 失败"
        name = platform_names.get(platform, platform)
        print(f"  [{platform.upper()}] {name:12} - {status} (耗时: {duration:.1f}秒)")

    if success_count < len(PLATFORMS):
        print(f"\n失败的平台:")
        for platform, success, _ in results:
            if not success:
                name = platform_names.get(platform, platform)
                log_file = Path(__file__).parent / f"logs/{platform}_crawl.log"
                print(f"  ❌ {name:12} - 查看日志: {log_file}")

    print(f"\n💾 数据保存位置: /Users/sunminghao/Desktop/MediaCrawler/data/")
    print(f"📋 日志保存位置: /Users/sunminghao/Desktop/MediaCrawler/logs/")
    print("="*70 + "\n")

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
        import traceback
        traceback.print_exc()
        sys.exit(1)
