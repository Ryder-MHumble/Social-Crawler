#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bilibili creator discovery script.

Search videos by keyword, collect creator profiles, fetch a sample of each
creator's recent videos, then export a ranked CSV.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import async_playwright

_SCRIPT_PATH = Path(__file__).resolve()
_SCRIPT_DIR = _SCRIPT_PATH.parent
_PROJECT_ROOT = _SCRIPT_PATH.parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

import config as base_config
from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.exception import DataFetchError
from media_platform.bilibili.field import SearchOrderType
from tools import runtime_paths, utils

DEFAULT_KEYWORDS = [
    "openclaw教程",
    "openclaw使用",
    "openclaw",
    "小龙虾编程",
]
DEFAULT_MAX_PAGES_PER_KEYWORD = 3
DEFAULT_MAX_VIDEOS_PER_CREATOR = 20
SLEEP_SEC = 1.5


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").replace("\n", ",").split(",") if item.strip()]


def _parse_metric(value: object) -> int:
    raw = str(value or "").strip().lower().replace(",", "")
    if not raw:
        return 0
    if "万" in raw:
        try:
            return int(float(raw.replace("万", "")) * 10000)
        except ValueError:
            return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _extract_seed_creator_ids(raw: str) -> dict[int, str]:
    seeds: dict[int, str] = {}
    for item in _split_csv(raw):
        match = re.search(r"space\.bilibili\.com/(\d+)", item)
        creator_id = match.group(1) if match else re.sub(r"\D+", "", item)
        if creator_id:
            seeds[int(creator_id)] = "seed"
    return seeds


def _default_output_csv() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(_SCRIPT_DIR / f"bili_creators_{timestamp}.csv")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bilibili creator discovery crawler")
    parser.add_argument(
        "--keywords",
        default=",".join(DEFAULT_KEYWORDS),
        help="Comma-separated discovery keywords.",
    )
    parser.add_argument(
        "--max-pages-per-keyword",
        type=int,
        default=DEFAULT_MAX_PAGES_PER_KEYWORD,
        help="Maximum search pages per keyword.",
    )
    parser.add_argument(
        "--max-videos-per-creator",
        type=int,
        default=DEFAULT_MAX_VIDEOS_PER_CREATOR,
        help="Maximum number of videos fetched per creator.",
    )
    parser.add_argument(
        "--output-csv",
        default=_default_output_csv(),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--seed-creator-ids",
        default="",
        help="Comma-separated creator UIDs or Bilibili profile URLs to include directly.",
    )
    return parser.parse_args()


async def search_videos_by_keyword(
    client: BilibiliClient,
    keyword: str,
    max_pages: int,
) -> List[Dict]:
    all_videos = []
    page_size = 20
    for page in range(1, max_pages + 1):
        utils.logger.info(f"[Search] keyword={keyword!r} page={page}")
        try:
            res = await client.search_video_by_keyword(
                keyword=keyword,
                page=page,
                page_size=page_size,
                order=SearchOrderType.DEFAULT,
            )
            video_list: List[Dict] = res.get("result") or []
            if not video_list:
                utils.logger.info(f"[Search] keyword={keyword!r} page={page} no results, stop")
                break
            all_videos.extend(video_list)
            utils.logger.info(f"[Search] keyword={keyword!r} page={page} got={len(video_list)}")
        except DataFetchError as exc:
            utils.logger.error(f"[Search] keyword={keyword!r} page={page} failed: {exc}")
            break
        await asyncio.sleep(SLEEP_SEC)
    return all_videos


async def get_creator_info(client: BilibiliClient, uid: int) -> Optional[Dict]:
    try:
        return await client.get_creator_info(uid)
    except DataFetchError as exc:
        utils.logger.error(f"[Creator] uid={uid} profile fetch failed: {exc}")
        return None


async def get_creator_videos(
    client: BilibiliClient,
    uid: int,
    max_videos: int,
) -> List[Dict]:
    videos = []
    pn = 1
    ps = min(30, max_videos)
    while len(videos) < max_videos:
        try:
            result = await client.get_creator_videos(uid, pn=pn, ps=ps)
        except DataFetchError as exc:
            utils.logger.error(f"[Creator] uid={uid} page={pn} video fetch failed: {exc}")
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
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


async def main() -> None:
    args = _parse_args()
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    max_pages_per_keyword = max(1, args.max_pages_per_keyword)
    max_videos_per_creator = max(1, args.max_videos_per_creator)
    output_csv = args.output_csv or _default_output_csv()
    seed_creators = _extract_seed_creator_ids(args.seed_creator_ids)

    utils.logger.info("=" * 60)
    utils.logger.info("Bilibili creator discovery started")
    utils.logger.info(f"Keywords: {keywords}")
    if seed_creators:
        utils.logger.info(f"Seed creators: {list(seed_creators.keys())}")
    utils.logger.info(f"Output: {output_csv}")
    utils.logger.info("=" * 60)

    async with async_playwright() as playwright:
        chromium = playwright.chromium
        runtime_paths.ensure_runtime_layout()
        user_data_dir = runtime_paths.get_browser_user_data_dir(
            "bili",
            getattr(base_config, "USER_DATA_DIR", "user_data_%s"),
        )
        user_agent = utils.get_user_agent()

        if getattr(base_config, "SAVE_LOGIN_STATE", False) and user_data_dir.exists():
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
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

        stealth_path = runtime_paths.get_repo_path("libs", "stealth.min.js")
        if stealth_path.exists():
            await browser_context.add_init_script(path=str(stealth_path))

        page = await browser_context.new_page()
        await page.goto("https://www.bilibili.com")

        from tools import utils as _utils

        cookie_str, cookie_dict = _utils.convert_cookies(await browser_context.cookies())
        if not cookie_dict:
            try:
                from cookies_config import BILIBILI_COOKIE

                if BILIBILI_COOKIE:
                    utils.logger.info("[Init] Using Bilibili cookie from cookies_config.py")
                    cookie_str = BILIBILI_COOKIE
                    cookie_dict = dict(
                        item.split("=", 1)
                        for item in BILIBILI_COOKIE.split("; ")
                        if "=" in item
                    )
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

        is_logged_in = await client.pong()
        if not is_logged_in:
            utils.logger.warning("[Init] Cookie may be expired; continuing in limited mode")
        else:
            utils.logger.info("[Init] Login status looks valid")

        uid_set: Dict[int, dict[str, object]] = {
            uid: {"name": "", "keywords": {source}}
            for uid, source in seed_creators.items()
        }
        for keyword in keywords:
            videos = await search_videos_by_keyword(client, keyword, max_pages_per_keyword)
            for video in videos:
                uid = video.get("mid") or video.get("author_mid")
                name = video.get("author", "")
                if uid:
                    bucket = uid_set.setdefault(int(uid), {"name": "", "keywords": set()})
                    if name and not bucket.get("name"):
                        bucket["name"] = name
                    keywords_bucket = bucket.get("keywords")
                    if isinstance(keywords_bucket, set):
                        keywords_bucket.add(keyword)
            utils.logger.info(f"[Summary] keyword={keyword!r} unique creators={len(uid_set)}")

        utils.logger.info(f"[Summary] total unique creators={len(uid_set)}")
        creators = []

        for index, (uid, meta) in enumerate(uid_set.items(), start=1):
            fallback_name = str(meta.get("name", "") or "")
            utils.logger.info(f"[Progress] {index}/{len(uid_set)} uid={uid} name={fallback_name}")
            info = await get_creator_info(client, uid)
            await asyncio.sleep(SLEEP_SEC)
            if info is None:
                utils.logger.warning(f"[Progress] skip uid={uid}, failed to fetch profile")
                continue

            name = info.get("name", fallback_name)
            fans = info.get("follower", 0)
            sign = info.get("sign", "")
            creator_videos = await get_creator_videos(client, uid, max_videos_per_creator)
            await asyncio.sleep(SLEEP_SEC)

            video_summaries = []
            representative_titles: list[str] = []
            total_play = 0
            total_comment = 0
            total_favorite = 0
            for video in creator_videos:
                bvid = video.get("bvid", "")
                title = video.get("title", "")
                play = _parse_metric(video.get("play", 0))
                comment_count = _parse_metric(
                    video.get("comment")
                    or video.get("video_review_count")
                    or video.get("video_comment")
                    or 0
                )
                favorite_count = _parse_metric(
                    video.get("favorite")
                    or video.get("favorites")
                    or video.get("video_favorite_count")
                    or 0
                )
                pubdate = video.get("created", 0)
                pub_str = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d") if pubdate else ""
                video_url = f"https://www.bilibili.com/video/{bvid}"
                video_summaries.append(f"{title}|{video_url}|播放{play}|{pub_str}")
                if title and len(representative_titles) < 3:
                    representative_titles.append(title)
                total_play += play
                total_comment += comment_count
                total_favorite += favorite_count
            average_play = int(total_play / len(creator_videos)) if creator_videos else 0

            creators.append(
                {
                    "uid": uid,
                    "name": name,
                    "fans": fans,
                    "fans_formatted": format_fans(fans),
                    "sign": sign,
                    "profile_url": f"https://space.bilibili.com/{uid}",
                    "video_count": len(creator_videos),
                    "videos": " ;; ".join(video_summaries),
                    "representative_titles": representative_titles,
                    "total_play": total_play,
                    "total_comment": total_comment,
                    "total_favorite": total_favorite,
                    "average_play": average_play,
                    "discovery_keyword": ",".join(
                        sorted(str(item) for item in meta.get("keywords", set()))
                    ),
                }
            )
            utils.logger.info(
                f"[Creator] {name} fans={format_fans(fans)} videos={len(creator_videos)}"
            )

        creators.sort(key=lambda item: item["fans"], reverse=True)
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as fp:
            fieldnames = [
                "排名",
                "博主ID",
                "博主名称",
                "粉丝数",
                "粉丝数(格式化)",
                "简介",
                "主页链接",
                "代表视频1",
                "代表视频2",
                "代表视频3",
                "总播放量",
                "总评论量",
                "总收藏量",
                "平均播放量",
                "视频数量",
                "发现关键词",
                "视频列表(标题|URL|播放量|发布日期)",
                "uid",
                "名称",
                "主页URL",
            ]
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            for rank, creator in enumerate(creators, start=1):
                representative_titles = list(creator["representative_titles"])
                writer.writerow(
                    {
                        "排名": rank,
                        "博主ID": creator["uid"],
                        "博主名称": creator["name"],
                        "uid": creator["uid"],
                        "名称": creator["name"],
                        "粉丝数": creator["fans"],
                        "粉丝数(格式化)": creator["fans_formatted"],
                        "简介": creator["sign"],
                        "主页链接": creator["profile_url"],
                        "主页URL": creator["profile_url"],
                        "代表视频1": representative_titles[0] if len(representative_titles) > 0 else "",
                        "代表视频2": representative_titles[1] if len(representative_titles) > 1 else "",
                        "代表视频3": representative_titles[2] if len(representative_titles) > 2 else "",
                        "总播放量": creator["total_play"],
                        "总评论量": creator["total_comment"],
                        "总收藏量": creator["total_favorite"],
                        "平均播放量": creator["average_play"],
                        "视频数量": creator["video_count"],
                        "发现关键词": creator["discovery_keyword"],
                        "视频列表(标题|URL|播放量|发布日期)": creator["videos"],
                    }
                )

        utils.logger.info("=" * 60)
        utils.logger.info(f"Completed, saved {len(creators)} creators")
        utils.logger.info(f"Output: {output_csv}")
        utils.logger.info("=" * 60)
        await browser_context.close()


if __name__ == "__main__":
    asyncio.run(main())
