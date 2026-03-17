#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站openclaw相关博主信息爬取脚本
爬取关键词：openclaw教程、openclaw使用、小龙虾等
输出：CSV文件，包含博主主页URL、名称、粉丝数、对应的视频信息
"""

import asyncio
import csv
import os
from datetime import datetime
from typing import Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page

import config
from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.field import SearchOrderType
from tools import utils


class OpenclawCreatorCrawler:
    def __init__(self):
        self.index_url = "https://www.bilibili.com"
        self.user_agent = utils.get_user_agent()
        self.keywords = ["openclaw教程", "openclaw使用", "小龙虾", "openclaw"]
        self.creator_data = {}  # {creator_id: {info, videos}}

    async def start(self):
        """启动爬虫"""
        async with async_playwright() as playwright:
            chromium = playwright.chromium
            self.browser_context = await self.launch_browser(chromium)
            await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            # 创建客户端
            self.bili_client = await self.create_bilibili_client()

            # 检查登录状态
            if not await self.bili_client.pong():
                utils.logger.warning("未登录，可能无法获取完整数据")

            # 搜索关键词并收集博主信息
            await self.search_and_collect()

            # 保存为CSV
            await self.save_to_csv()

            await self.browser_context.close()

    async def launch_browser(self, chromium) -> BrowserContext:
        """启动浏览器"""
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(os.getcwd(), "browser_data", config.USER_DATA_DIR % "bilibili")
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=config.HEADLESS,
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent,
                channel="chrome",
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=config.HEADLESS, channel="chrome")
            browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent
            )
            return browser_context

    async def create_bilibili_client(self) -> BilibiliClient:
        """创建B站客户端"""
        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())
        bilibili_client_obj = BilibiliClient(
            proxy=None,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com",
                "Content-Type": "application/json;charset=UTF-8",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
            proxy_ip_pool=None,
        )
        return bilibili_client_obj

    async def search_and_collect(self):
        """搜索关键词并收集博主信息"""
        utils.logger.info("[OpenclawCreatorCrawler] 开始搜索关键词...")

        for keyword in self.keywords:
            utils.logger.info(f"[OpenclawCreatorCrawler] 搜索关键词: {keyword}")
            page = 1
            max_pages = 5  # 每个关键词搜索5页

            while page <= max_pages:
                try:
                    videos_res = await self.bili_client.search_video_by_keyword(
                        keyword=keyword,
                        page=page,
                        page_size=20,
                        order=SearchOrderType.DEFAULT,
                        pubtime_begin_s=0,
                        pubtime_end_s=0,
                    )

                    video_list: List[Dict] = videos_res.get("result", [])
                    if not video_list:
                        utils.logger.info(f"[OpenclawCreatorCrawler] 关键词 '{keyword}' 第{page}页无结果")
                        break

                    # 处理每个视频，提取博主信息
                    for video_item in video_list:
                        await self.process_video(video_item, keyword)

                    page += 1
                    await asyncio.sleep(2)  # 避免请求过快

                except Exception as e:
                    utils.logger.error(f"[OpenclawCreatorCrawler] 搜索出错: {e}")
                    break

        utils.logger.info(f"[OpenclawCreatorCrawler] 共收集到 {len(self.creator_data)} 个博主")

    async def process_video(self, video_item: Dict, keyword: str):
        """处理单个视频，提取博主和视频信息"""
        try:
            # 提取博主信息
            creator_id = video_item.get("mid")
            creator_name = video_item.get("author")

            if not creator_id:
                return

            # 提取视频信息
            video_info = {
                "title": video_item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                "bvid": video_item.get("bvid", ""),
                "aid": video_item.get("aid", ""),
                "play": video_item.get("play", 0),  # 播放量
                "video_review": video_item.get("video_review", 0),  # 评论数
                "favorites": video_item.get("favorites", 0),  # 收藏数
                "description": video_item.get("description", ""),
                "pubdate": video_item.get("pubdate", 0),
                "keyword": keyword,
            }

            # 如果博主不在字典中，获取详细信息
            if creator_id not in self.creator_data:
                utils.logger.info(f"[OpenclawCreatorCrawler] 获取博主信息: {creator_name} (ID: {creator_id})")

                try:
                    creator_detail = await self.bili_client.get_creator_info(int(creator_id))

                    self.creator_data[creator_id] = {
                        "id": creator_id,
                        "name": creator_detail.get("name", creator_name),
                        "fans": creator_detail.get("follower", 0),  # 粉丝数
                        "sign": creator_detail.get("sign", ""),  # 签名
                        "avatar": creator_detail.get("face", ""),
                        "homepage": f"https://space.bilibili.com/{creator_id}",
                        "videos": []
                    }
                    await asyncio.sleep(1)  # 避免请求过快
                except Exception as e:
                    utils.logger.error(f"[OpenclawCreatorCrawler] 获取博主详情失败: {e}")
                    # 使用基本信息
                    self.creator_data[creator_id] = {
                        "id": creator_id,
                        "name": creator_name,
                        "fans": 0,
                        "sign": "",
                        "avatar": "",
                        "homepage": f"https://space.bilibili.com/{creator_id}",
                        "videos": []
                    }

            # 添加视频到博主的视频列表
            self.creator_data[creator_id]["videos"].append(video_info)

        except Exception as e:
            utils.logger.error(f"[OpenclawCreatorCrawler] 处理视频出错: {e}")

    async def save_to_csv(self):
        """保存数据到CSV文件（去重版本）"""
        # 对每个博主的视频进行去重（基于bvid）
        for creator_id, creator_info in self.creator_data.items():
            seen_bvids = set()
            unique_videos = []
            for video in creator_info["videos"]:
                bvid = video["bvid"]
                if bvid not in seen_bvids:
                    seen_bvids.add(bvid)
                    unique_videos.append(video)
            creator_info["videos"] = unique_videos

        # 按播放量总和排序（因为粉丝数都是0）
        sorted_creators = sorted(
            self.creator_data.values(),
            key=lambda x: sum(v["play"] for v in x["videos"]),
            reverse=True
        )

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"openclaw_creators_{timestamp}.csv"
        filepath = os.path.join(os.getcwd(), filename)

        utils.logger.info(f"[OpenclawCreatorCrawler] 保存数据到: {filepath}")

        # 统计信息
        total_videos = sum(len(c["videos"]) for c in sorted_creators)

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow([
                "博主ID",
                "博主名称",
                "粉丝数",
                "主页URL",
                "签名",
                "视频数量",
                "总播放量",
                "视频标题",
                "视频BV号",
                "视频播放量",
                "视频评论数",
                "视频收藏数",
                "视频描述",
                "发布时间",
                "匹配关键词"
            ])

            # 写入数据
            for creator in sorted_creators:
                video_count = len(creator["videos"])
                total_play = sum(v["play"] for v in creator["videos"])

                if not creator["videos"]:
                    # 如果没有视频，只写博主信息
                    writer.writerow([
                        creator["id"],
                        creator["name"],
                        creator["fans"],
                        creator["homepage"],
                        creator["sign"],
                        0,
                        0,
                        "", "", "", "", "", "", "", ""
                    ])
                else:
                    # 每个视频一行
                    for idx, video in enumerate(creator["videos"]):
                        # 转换时间戳
                        pubdate_str = datetime.fromtimestamp(video["pubdate"]).strftime("%Y-%m-%d %H:%M:%S") if video["pubdate"] else ""

                        writer.writerow([
                            creator["id"],
                            creator["name"],
                            creator["fans"],
                            creator["homepage"],
                            creator["sign"],
                            video_count if idx == 0 else "",  # 只在第一行显示
                            total_play if idx == 0 else "",   # 只在第一行显示
                            video["title"],
                            video["bvid"],
                            video["play"],
                            video["video_review"],
                            video["favorites"],
                            video["description"][:100],  # 限制描述长度
                            pubdate_str,
                            video["keyword"]
                        ])

        utils.logger.info(f"[OpenclawCreatorCrawler] 数据已保存到: {filepath}")
        utils.logger.info(f"[OpenclawCreatorCrawler] 共保存 {len(sorted_creators)} 个博主，{total_videos} 个视频（已去重）")


async def main():
    crawler = OpenclawCreatorCrawler()
    await crawler.start()


if __name__ == "__main__":
    asyncio.run(main())
