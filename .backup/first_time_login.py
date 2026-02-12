#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
First time login helper script
Helps you login to all platforms one by one before using parallel crawling

Usage:
    python first_time_login.py
"""

import subprocess
import sys
from pathlib import Path

# Keywords to search (comma-separated)
KEYWORDS = "中关村人工智能研究院,北京中关村学院"

# Platforms to setup
PLATFORMS = ["xhs", "dy", "bili", "wb"]  # xhs = 小红书, dy = 抖音, bili = B站, wb = 微博

# Common settings
LOGIN_TYPE = "qrcode"  # Use QR code login
CRAWLER_TYPE = "search"  # Search mode
SAVE_DATA_OPTION = "json"  # Save as JSON files
ENABLE_COMMENTS = "yes"  # Crawl comments


def check_login_status(platform: str) -> bool:
    """
    Check if platform login status exists

    Args:
        platform: Platform name

    Returns:
        bool: True if login cache exists
    """
    user_data_dir = Path(__file__).parent / f"{platform}_user_data_dir"
    return user_data_dir.exists()


def run_platform_login(platform: str):
    """
    Run the crawler for a platform to perform login

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

    print(f"\n{'='*70}")
    print(f"准备登录: {platform_names.get(platform, platform)} ({platform.upper()})")
    print(f"{'='*70}\n")

    # Check if already logged in
    if check_login_status(platform):
        print(f"✅ 检测到 {platform_names.get(platform, platform)} 已有登录缓存")
        skip = input("是否跳过此平台? (y/n, 默认: y): ").strip().lower()
        if skip in ['', 'y', 'yes']:
            print(f"⏭️  跳过 {platform_names.get(platform, platform)}")
            return True

    print(f"📱 请准备好 {platform_names.get(platform, platform)} APP，准备扫码登录")
    print(f"💡 浏览器窗口将会打开，请使用 {platform_names.get(platform, platform)} APP 扫描二维码")
    print(f"⚠️  登录成功后，脚本会自动开始爬取，完成后会自动退出\n")

    input("按 Enter 键继续...")

    # Build command - only crawl 1 post for quick login test
    cmd = [
        "uv", "run", "main.py",
        "--platform", platform,
        "--lt", LOGIN_TYPE,
        "--type", CRAWLER_TYPE,
        "--keywords", KEYWORDS.split(',')[0],  # Only use first keyword
        "--save_data_option", SAVE_DATA_OPTION,
        "--get_comment", "no",  # Don't crawl comments for quick test
    ]

    try:
        # Run the command
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            cwd=Path(__file__).parent
        )

        print(f"\n✅ {platform_names.get(platform, platform)} 登录成功并完成测试爬取！")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ {platform_names.get(platform, platform)} 登录失败！")
        print(f"错误信息: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断了 {platform_names.get(platform, platform)} 的登录")
        return False


def main():
    """
    Main function to help setup login for all platforms
    """
    print("\n" + "="*70)
    print("🔐 首次登录辅助工具")
    print("="*70)
    print("此工具将帮助你逐个完成所有平台的登录设置")
    print("完成后，你就可以使用并行爬虫脚本了！")
    print("="*70 + "\n")

    print("📋 需要登录的平台:")
    platform_names = {
        "xhs": "小红书",
        "dy": "抖音",
        "bili": "Bilibili",
        "wb": "微博"
    }
    for i, platform in enumerate(PLATFORMS, 1):
        status = "✅ 已登录" if check_login_status(platform) else "❌ 未登录"
        print(f"  {i}. {platform_names.get(platform, platform):12} ({platform.upper()}) - {status}")

    print("\n⚠️  注意事项:")
    print("1. 每个平台需要单独扫码登录一次")
    print("2. 登录成功后会自动保存登录状态")
    print("3. 登录后会进行一次快速测试爬取（不爬取评论）")
    print("4. 完成所有平台登录后，即可使用并行爬虫脚本")
    print("5. 如果某个平台已登录，可以选择跳过\n")

    response = input("是否继续? (y/n): ").strip().lower()
    if response not in ['y', 'yes']:
        print("已取消")
        sys.exit(0)

    success_count = 0
    skipped_count = 0

    for i, platform in enumerate(PLATFORMS, 1):
        print(f"\n{'='*70}")
        print(f"进度: {i}/{len(PLATFORMS)}")
        print(f"{'='*70}")

        if check_login_status(platform):
            skipped_count += 1

        success = run_platform_login(platform)
        if success:
            success_count += 1

        # Ask if continue to next platform
        if i < len(PLATFORMS):
            print("\n" + "-"*70)
            next_platform = PLATFORMS[i]
            next_name = platform_names.get(next_platform, next_platform)
            response = input(f"准备登录下一个平台 ({next_name})，是否继续? (y/n): ").strip().lower()
            if response not in ['y', 'yes']:
                print("\n用户选择停止")
                break

    # Summary
    print("\n" + "="*70)
    print("📊 登录设置完成总结")
    print("="*70)
    print(f"✅ 成功: {success_count}/{len(PLATFORMS)} 个平台")

    if success_count == len(PLATFORMS):
        print("\n🎉 所有平台登录设置完成！")
        print("\n下一步:")
        print("  运行并行爬虫脚本:")
        print("    python auto_crawl_parallel.py")
        print("  或:")
        print("    ./auto_crawl_parallel.sh")
    else:
        print("\n⚠️  部分平台未完成登录设置")
        print("你可以:")
        print("  1. 重新运行此脚本完成剩余平台的登录")
        print("  2. 或者只爬取已登录的平台")

    print(f"\n💾 数据保存位置: /Users/sunminghao/Desktop/MediaCrawler/data/")
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
