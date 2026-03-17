#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站博主信息爬取脚本
按关键词搜索视频，收集 UP 主信息，获取粉丝数和视频列表，按粉丝数排序后保存为 CSV。

用法:
    python crawl_bili_creators.py
"""

import asyncio
import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from playwright.async_api import async_playwright

# 确保项目根目录在 path 中（此脚本在 scripts/bili_creator_crawler/ 下，需上溯两级）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)  # 保证相对路径（libs/stealth.min.js 等）可找到

import config as base_config
from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.field import SearchOrderType
from media_platform.bilibili.exception import DataFetchError
from tools import utils

# ============================================================
# 配置区域 — 按需修改
# ============================================================

KEYWORDS = [
    "openclaw教程",
    "openclaw使用",
    "openclaw",
    "小龙虾编程",
]

# 每个关键词最多爬取几页（每页20条视频）
MAX_PAGES_PER_KEYWORD = 3

# 每个UP主最多获取多少条视频
MAX_VIDEOS_PER_CREATOR = 20

# 请求间隔（秒），避免触发风控
SLEEP_SEC = 1.5

# 输出 CSV 路径（保存在脚本同目录下）
OUTPUT_CSV = os.path.join(_SCRIPT_DIR, f"bili_creators_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# ============================================================


async def search_videos_by_keyword(
    client: BilibiliClient,
    keyword: str,
    max_pages: int = 3,
) -> List[Dict]:
    """搜索关键词，返回视频列表（原始搜索结果条目）。"""
    all_videos = []
    page_size = 20
    for page in range(1, max_pages + 1):
        utils.logger.info(f"[搜索] 关键词={keyword!r} 第{page}页")
        try:
            res = await client.search_video_by_keyword(
                keyword=keyword,
                page=page,
                page_size=page_size,
                order=SearchOrderType.DEFAULT,
            )
            video_list: List[Dict] = res.get("result") or []
            if not video_list:
                utils.logger.info(f"[搜索] 关键词={keyword!r} 第{page}页无结果，停止")
                break
            all_videos.extend(video_list)
            utils.logger.info(f"[搜索] 关键词={keyword!r} 第{page}页获得{len(video_list)}条")
        except DataFetchError as e:
            utils.logger.error(f"[搜索] 关键词={keyword!r} 第{page}页失败: {e}")
            break
        await asyncio.sleep(SLEEP_SEC)
    return all_videos


async def get_creator_info(client: BilibiliClient, uid: int) -> Optional[Dict]:
    """获取UP主基本信息（含粉丝数等）。"""
    try:
        info = await client.get_creator_info(uid)
        return info
    except DataFetchError as e:
        utils.logger.error(f"[UP主信息] uid={uid} 失败: {e}")
        return None


async def get_creator_videos(
    client: BilibiliClient,
    uid: int,
    max_videos: int = 20,
) -> List[Dict]:
    """获取UP主的视频列表（bvid、标题、播放量、发布时间）。"""
    videos = []
    pn = 1
    ps = min(30, max_videos)
    while len(videos) < max_videos:
        try:
            result = await client.get_creator_videos(uid, pn=pn, ps=ps)
        except DataFetchError as e:
            utils.logger.error(f"[UP主视频] uid={uid} 第{pn}页失败: {e}")
            break
        vlist: List[Dict] = result.get("list", {}).get("vlist", [])
        if not vlist:
            break
        videos.extend(vlist)
        page_info: Dict = result.get("page", {})
        total = int(page_info.get("count", 0))
        if len(videos) >= total or len(videos) >= max_videos:
            break
        pn += 1
        await asyncio.sleep(SLEEP_SEC)
    return videos[:max_videos]


def format_fans(n: int) -> str:
    """将粉丝数格式化为易读字符串。"""
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


async def main():
    utils.logger.info("=" * 60)
    utils.logger.info("B站博主信息爬取脚本启动")
    utils.logger.info(f"关键词: {KEYWORDS}")
    utils.logger.info(f"输出文件: {OUTPUT_CSV}")
    utils.logger.info("=" * 60)

    async with async_playwright() as playwright:
        chromium = playwright.chromium

        # 尝试使用已保存的登录状态，否则用 cookie 字符串
        user_data_dir = os.path.join(
            os.getcwd(), "browser_data",
            getattr(base_config, "USER_DATA_DIR", "user_data_%s") % "bili",
        )

        user_agent = utils.get_user_agent()

        if getattr(base_config, "SAVE_LOGIN_STATE", False) and os.path.exists(user_data_dir):
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=getattr(base_config, "HEADLESS", True),
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                channel="chrome",
            )
        else:
            browser = await chromium.launch(
                headless=getattr(base_config, "HEADLESS", True),
                channel="chrome",
            )
            browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
            )

        # 注入 stealth.min.js
        stealth_path = os.path.join(os.getcwd(), "libs", "stealth.min.js")
        if os.path.exists(stealth_path):
            await browser_context.add_init_script(path=stealth_path)

        page = await browser_context.new_page()
        await page.goto("https://www.bilibili.com")

        # 注入 cookie
        from tools import utils as _utils
        cookie_str, cookie_dict = _utils.convert_cookies(await browser_context.cookies())

        # 如果 cookie 为空，则使用配置文件中的 cookie
        if not cookie_dict:
            try:
                from cookies_config import BILIBILI_COOKIE
                if BILIBILI_COOKIE:
                    utils.logger.info("[init] 使用 cookies_config.py 中的 Bilibili Cookie")
                    cookie_str = BILIBILI_COOKIE
                    cookie_dict = dict(item.split("=", 1) for item in BILIBILI_COOKIE.split("; ") if "=" in item)
            except ImportError:
                pass

        client = BilibiliClient(
            proxy=None,
            headers={
                "User-Agent": user_agent,
                "Cookie": cookie_str,
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com",
                "Content-Type": "application/json;charset=UTF-8",
            },
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        # 检查登录状态
        is_logged_in = await client.pong()
        if not is_logged_in:
            utils.logger.warning("[init] Cookie 可能已过期，将以未登录状态继续（部分数据可能受限）")
        else:
            utils.logger.info("[init] 登录状态正常")

        # ---- 第一步：搜索关键词，收集 UP 主 UID ----
        # uid -> {uid, name, mid_from_search}
        uid_set: Dict[int, str] = {}  # uid -> name（from search）

        for keyword in KEYWORDS:
            videos = await search_videos_by_keyword(client, keyword, MAX_PAGES_PER_KEYWORD)
            for v in videos:
                uid = v.get("mid") or v.get("author_mid")
                name = v.get("author", "")
                if uid:
                    uid_set[int(uid)] = name
            utils.logger.info(f"[汇总] 关键词={keyword!r} 累计UP主数: {len(uid_set)}")

        utils.logger.info(f"[汇总] 共找到 {len(uid_set)} 个不重复UP主")

        # ---- 第二步：逐一获取 UP 主详细信息 + 视频 ----
        creators = []

        for i, (uid, fallback_name) in enumerate(uid_set.items(), 1):
            utils.logger.info(f"[进度] {i}/{len(uid_set)} — uid={uid} name={fallback_name}")

            info = await get_creator_info(client, uid)
            await asyncio.sleep(SLEEP_SEC)

            if info is None:
                utils.logger.warning(f"  跳过 uid={uid}（获取信息失败）")
                continue

            name = info.get("name", fallback_name)
            fans = info.get("follower", 0)
            sign = info.get("sign", "")

            # 获取视频列表
            videos_of_creator = await get_creator_videos(client, uid, MAX_VIDEOS_PER_CREATOR)
            await asyncio.sleep(SLEEP_SEC)

            # 整理视频信息
            video_summaries = []
            for v in videos_of_creator:
                bvid = v.get("bvid", "")
                title = v.get("title", "")
                play = v.get("play", 0)
                pubdate = v.get("created", 0)
                pub_str = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d") if pubdate else ""
                video_url = f"https://www.bilibili.com/video/{bvid}"
                video_summaries.append(f"{title}|{video_url}|播放{play}|{pub_str}")

            creators.append({
                "uid": uid,
                "name": name,
                "fans": fans,
                "fans_formatted": format_fans(fans),
                "sign": sign,
                "profile_url": f"https://space.bilibili.com/{uid}",
                "video_count": len(videos_of_creator),
                "videos": " ;; ".join(video_summaries),
            })

            utils.logger.info(f"  {name} — 粉丝: {format_fans(fans)} — 视频数: {len(videos_of_creator)}")

        # ---- 第三步：按粉丝数降序排列，保存 CSV ----
        creators.sort(key=lambda x: x["fans"], reverse=True)

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["排名", "uid", "名称", "粉丝数", "粉丝数(格式化)", "简介", "主页URL", "视频数量", "视频列表(标题|URL|播放量|发布日期)"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rank, c in enumerate(creators, 1):
                writer.writerow({
                    "排名": rank,
                    "uid": c["uid"],
                    "名称": c["name"],
                    "粉丝数": c["fans"],
                    "粉丝数(格式化)": c["fans_formatted"],
                    "简介": c["sign"],
                    "主页URL": c["profile_url"],
                    "视频数量": c["video_count"],
                    "视频列表(标题|URL|播放量|发布日期)": c["videos"],
                })

        utils.logger.info("=" * 60)
        utils.logger.info(f"完成！共保存 {len(creators)} 个UP主信息")
        utils.logger.info(f"输出文件: {OUTPUT_CSV}")
        utils.logger.info("=" * 60)

        await browser_context.close()


if __name__ == "__main__":
    asyncio.run(main())
