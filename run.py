#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MediaCrawler 统一运行脚本
自动检查登录状态，引导登录，然后开始并行爬取

Usage:
    python run.py              # 正常模式：检查登录 -> 并行爬取
    python run.py --login-only # 仅登录模式
    python run.py --crawl-only # 仅爬取模式（跳过登录检查）
"""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse

# 导入 Cookie 配置
try:
    import cookies_config
    COOKIES_AVAILABLE = True
except ImportError:
    COOKIES_AVAILABLE = False
    cookies_config = None

# ==================== 配置区域 ====================
# 关键词配置
# 用精确的机构全称搜索，结合 RELEVANCE_MUST_CONTAIN 过滤确保只保存相关内容
KEYWORDS = "中关村人工智能研究院,北京中关村学院,中关村学院,中关村 河套 创智"
# 喜欢对比上海创智、深圳河套还有上海AI Lab

# 平台配置
PLATFORMS = ["xhs", "dy", "bili", "zhihu"]  # xhs=小红书, dy=抖音, bili=B站, zhihu=知乎

# 爬取配置
LOGIN_TYPE = "qrcode"  # cookie 或 qrcode (优先使用 Cookie 登录)
CRAWLER_TYPE = "search"
SAVE_DATA_OPTION = "supabase"
ENABLE_COMMENTS = "yes"

# 平台专属覆盖配置（不填则使用 base_config.py 中的默认值）
# max_notes_count: 每个关键词最多爬取多少条内容
PLATFORM_OVERRIDES: dict[str, dict] = {
    # xhs 不填，沿用 base_config.py 默认值（30条/关键词）
    "dy":    {"max_notes_count": 10},  # 抖音：内容质量参差，适当减量
    "bili":  {"max_notes_count": 15},  # B站：相关内容少，减量
    "zhihu": {"max_notes_count": 10},  # 知乎：内容冗杂，最少
}

# 平台名称映射
PLATFORM_NAMES = {
    "xhs": "小红书",
    "dy": "抖音",
    "bili": "Bilibili",
    "wb": "微博",
    "ks": "快手",
    "tieba": "贴吧",
    "zhihu": "知乎"
}
# ==================== 配置区域结束 ====================


def get_platform_cookie(platform: str) -> str:
    """
    获取指定平台的 Cookie

    Args:
        platform: 平台代码

    Returns:
        str: Cookie 字符串，如果未配置则返回空字符串
    """
    if not COOKIES_AVAILABLE or not cookies_config:
        return ""

    return cookies_config.get_cookie(platform)


def is_cookie_login_enabled() -> bool:
    """
    检查是否启用 Cookie 登录

    Returns:
        bool: True 表示启用 Cookie 登录
    """
    return LOGIN_TYPE == "cookie" and COOKIES_AVAILABLE


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           MediaCrawler 自动化爬虫系统                        ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

    # 显示登录方式
    if is_cookie_login_enabled():
        print("🔑 登录方式: Cookie 登录")
        configured = cookies_config.get_all_configured_platforms() if cookies_config else []
        if configured:
            print(f"✅ 已配置 Cookie 的平台: {', '.join([PLATFORM_NAMES.get(p, p) for p in configured])}")
        else:
            print("⚠️  未配置任何平台的 Cookie，请编辑 cookies_config.py")
    else:
        print("📱 登录方式: 扫码登录")
    print()


def check_login_status(platform: str) -> bool:
    """
    检查平台登录状态

    Args:
        platform: 平台代码

    Returns:
        bool: True表示已登录
    """
    user_data_dir = Path(__file__).parent / f"{platform}_user_data_dir"
    return user_data_dir.exists() and any(user_data_dir.iterdir())


def login_platform(platform: str) -> bool:
    """
    登录单个平台

    Args:
        platform: 平台代码

    Returns:
        bool: 登录是否成功
    """
    platform_name = PLATFORM_NAMES.get(platform, platform)

    print(f"\n{'='*70}")
    print(f"🔐 准备登录: {platform_name} ({platform.upper()})")
    print(f"{'='*70}\n")

    print(f"📱 请准备好 {platform_name} APP")
    print(f"💡 浏览器将打开，请扫描二维码登录")
    print(f"⚠️  登录成功后会自动完成测试爬取\n")

    input("按 Enter 键继续...")

    # 构建登录命令 - 只爬取少量数据用于测试
    cmd = [
        sys.executable, "main.py",
        "--platform", platform,
        "--lt", LOGIN_TYPE,
        "--type", CRAWLER_TYPE,
        "--keywords", KEYWORDS.split(',')[0],  # 只用第一个关键词
        "--save_data_option", SAVE_DATA_OPTION,
        "--get_comment", "no",  # 测试时不爬评论
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=Path(__file__).parent
        )

        print(f"\n✅ {platform_name} 登录成功！")
        return True

    except subprocess.CalledProcessError:
        print(f"\n❌ {platform_name} 登录失败")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  用户取消了 {platform_name} 的登录")
        return False


def check_and_login():
    """
    检查所有平台登录状态

    Returns:
        bool: 是否有可用的平台
    """
    # 如果使用 Cookie 登录，检查 Cookie 配置
    if is_cookie_login_enabled():
        print("\n" + "="*70)
        print("🔍 检查 Cookie 配置")
        print("="*70 + "\n")

        if not cookies_config:
            print("❌ 未找到 cookies_config.py 文件")
            print("📝 请参考 COOKIE_GUIDE.md 创建配置文件")
            return False

        configured_platforms = cookies_config.get_all_configured_platforms()
        need_config = []

        for platform in PLATFORMS:
            platform_name = PLATFORM_NAMES.get(platform, platform)
            is_configured = platform in configured_platforms

            status_text = "✅ 已配置" if is_configured else "❌ 未配置"
            print(f"  {platform_name:12} ({platform.upper()}) - {status_text}")

            if not is_configured:
                need_config.append(platform)

        if not need_config:
            print("\n🎉 所有平台的 Cookie 都已配置！")
            return True

        print(f"\n⚠️  {len(need_config)} 个平台未配置 Cookie: {', '.join([PLATFORM_NAMES.get(p, p) for p in need_config])}")
        print("📖 获取 Cookie 的方法请查看: COOKIE_GUIDE.md")

        if len(configured_platforms) > 0:
            print(f"\n✅ 将继续爬取已配置的 {len(configured_platforms)} 个平台")
            return True
        else:
            print("\n❌ 没有任何已配置的平台，无法爬取")
            return False

    # 使用扫码登录
    print("\n" + "="*70)
    print("🔍 检查登录状态")
    print("="*70 + "\n")

    login_status = {}
    need_login = []

    for platform in PLATFORMS:
        platform_name = PLATFORM_NAMES.get(platform, platform)
        is_logged_in = check_login_status(platform)
        login_status[platform] = is_logged_in

        status_text = "✅ 已登录" if is_logged_in else "❌ 未登录"
        print(f"  {platform_name:12} ({platform.upper()}) - {status_text}")

        if not is_logged_in:
            need_login.append(platform)

    if not need_login:
        print("\n🎉 所有平台都已登录！")
        return True

    print(f"\n⚠️  需要登录 {len(need_login)} 个平台: {', '.join([PLATFORM_NAMES.get(p, p) for p in need_login])}")

    # 逐个平台执行扫码登录
    for platform in need_login:
        success = login_platform(platform)
        if success:
            login_status[platform] = True

    # 统计最终已登录平台数
    logged_in_count = sum(1 for v in login_status.values() if v)
    if logged_in_count > 0:
        print(f"\n✅ 当前已登录 {logged_in_count}/{len(PLATFORMS)} 个平台")
        return True

    print("\n❌ 所有平台登录均失败")
    return False


def run_single_platform(platform: str):
    """
    运行单个平台的爬虫

    Args:
        platform: 平台代码

    Returns:
        tuple: (platform, success, duration)
    """
    platform_name = PLATFORM_NAMES.get(platform, platform)

    print(f"\n🚀 [{platform.upper()}] 开始爬取 {platform_name}...")

    start_time = time.time()

    # 构建命令
    cmd = [
        sys.executable, "main.py",
        "--platform", platform,
        "--lt", LOGIN_TYPE,
        "--type", CRAWLER_TYPE,
        "--keywords", KEYWORDS,
        "--save_data_option", SAVE_DATA_OPTION,
        "--get_comment", ENABLE_COMMENTS,
    ]

    # 应用平台专属覆盖配置
    overrides = PLATFORM_OVERRIDES.get(platform, {})
    if "max_notes_count" in overrides:
        cmd.extend(["--max_notes_count", str(overrides["max_notes_count"])])

    # 如果启用 Cookie 登录，添加 Cookie 参数
    if is_cookie_login_enabled():
        cookie = get_platform_cookie(platform)
        if cookie:
            cmd.extend(["--cookies", cookie])
            print(f"  🔑 [{platform.upper()}] 使用 Cookie 登录")
        else:
            print(f"  ⚠️  [{platform.upper()}] 未配置 {platform_name} 的 Cookie，将尝试使用缓存登录状态")

    try:
        subprocess.run(
            cmd,
            check=True,
            cwd=Path(__file__).parent
        )

        duration = time.time() - start_time
        print(f"\n✅ [{platform.upper()}] {platform_name} 爬取完成！耗时: {duration:.1f}秒")
        return (platform, True, duration)

    except subprocess.CalledProcessError:
        duration = time.time() - start_time
        print(f"\n❌ [{platform.upper()}] {platform_name} 爬取失败！")
        if is_cookie_login_enabled():
            print(f"💡 [{platform.upper()}] {platform_name} 的 Cookie 可能已失效，请更新 cookies_config.py")
        else:
            print(f"💡 [{platform.upper()}] 请检查登录状态或切换到 Cookie 登录")
        return (platform, False, duration)

    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ [{platform.upper()}] {platform_name} 爬取异常: {e}")
        return (platform, False, duration)


def parallel_crawl():
    """
    并行爬取所有平台（同时启动，各自独立进程）

    去重说明：各平台是独立子进程，内存不共享。
    跨平台的内容去重由 Supabase upsert + UNIQUE 约束保底；
    单平台内的跨关键词去重由 supabase_store_base.py 的 _seen_content_ids 处理。

    Returns:
        bool: 是否至少有一个平台成功
    """
    print("\n" + "="*70)
    print("🚀 开始并行爬取")
    print("="*70)
    print(f"\n目标关键词: {KEYWORDS}")
    print(f"爬取平台: {', '.join([PLATFORM_NAMES.get(p, p) for p in PLATFORMS])}")
    print(f"爬取方式: 所有平台同时启动")
    print(f"数据格式: {SAVE_DATA_OPTION.upper()}")
    print(f"登录方式: {LOGIN_TYPE.upper()}")
    if PLATFORM_OVERRIDES:
        for p, cfg in PLATFORM_OVERRIDES.items():
            name = PLATFORM_NAMES.get(p, p)
            overrides_str = ", ".join(f"{k}={v}" for k, v in cfg.items())
            print(f"  {name} 专属配置: {overrides_str}")
    print("\n" + "="*70 + "\n")

    start_time = time.time()
    results = []

    # 过滤掉未配置 Cookie 的平台（仅 Cookie 登录模式下）
    active_platforms = []
    for platform in PLATFORMS:
        platform_name = PLATFORM_NAMES.get(platform, platform)
        if is_cookie_login_enabled() and cookies_config:
            if not cookies_config.is_cookie_configured(platform):
                print(f"⚠️  [{platform.upper()}] {platform_name} 未配置 Cookie，跳过")
                results.append((platform, False, 0))
                continue
        active_platforms.append(platform)

    if not active_platforms:
        print("❌ 没有可爬取的平台")
        return False

    print(f"▶ 同时启动 {len(active_platforms)} 个平台的爬虫...\n")

    with ThreadPoolExecutor(max_workers=len(active_platforms)) as executor:
        futures = {executor.submit(run_single_platform, p): p for p in active_platforms}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                platform = futures[future]
                print(f"❌ [{platform.upper()}] 未捕获异常: {e}")
                results.append((platform, False, 0))

    total_duration = time.time() - start_time

    # 生成总结
    print("\n" + "="*70)
    print("📊 爬取任务完成总结")
    print("="*70 + "\n")

    success_count = sum(1 for _, success, _ in results if success)
    total_attempted = len(results)

    print(f"总体统计:")
    print(f"  ✅ 成功: {success_count}/{total_attempted} 个平台")
    print(f"  ⏱️  总耗时: {total_duration:.1f} 秒（并行，非累加）\n")

    print(f"详细结果:")
    for platform, success, duration in sorted(results, key=lambda x: x[0]):
        name = PLATFORM_NAMES.get(platform, platform)
        if success:
            print(f"  ✅ [{platform.upper()}] {name:12} - 成功 (耗时: {duration:.1f}秒)")
        else:
            if is_cookie_login_enabled() and cookies_config and not cookies_config.is_cookie_configured(platform):
                print(f"  ⚠️  [{platform.upper()}] {name:12} - 未配置 Cookie")
            else:
                print(f"  ❌ [{platform.upper()}] {name:12} - 失败 (Cookie可能已失效)")

    print(f"\n💾 数据保存位置: Supabase")
    print("="*70 + "\n")

    return success_count > 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MediaCrawler 自动化爬虫系统')
    parser.add_argument('--login-only', action='store_true', help='仅执行登录')
    parser.add_argument('--crawl-only', action='store_true', help='仅执行爬取（跳过登录检查）')
    args = parser.parse_args()

    print_banner()

    # 仅登录模式
    if args.login_only:
        print("🔐 登录模式\n")
        check_and_login()
        print("\n✅ 登录流程完成")
        return 0

    # 仅爬取模式
    if args.crawl_only:
        print("🚀 爬取模式（跳过登录检查）\n")
        success = parallel_crawl()
        return 0 if success else 1

    # 正常模式：检查登录 -> 并行爬取
    print("🔄 自动模式：检查登录状态 -> 并行爬取\n")

    # 步骤1: 检查登录状态
    has_available = check_and_login()

    if not has_available:
        print("\n❌ 没有可用的平台，请先配置 Cookie 或完成登录")
        print("📖 Cookie 配置指南: COOKIE_GUIDE.md")
        return 1

    # 步骤2: 并行爬取
    success = parallel_crawl()

    if success:
        print("\n🎉 爬取任务完成！")
        return 0
    else:
        print("\n⚠️  所有平台都失败了，请检查 Cookie 配置或查看日志")
        return 1


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
