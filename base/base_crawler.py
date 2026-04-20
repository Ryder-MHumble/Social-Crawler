# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/base/base_crawler.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

from abc import ABC, abstractmethod
from typing import Dict, Optional

from playwright.async_api import BrowserContext, BrowserType, Playwright


class AbstractCrawler(ABC):

    @abstractmethod
    async def start(self):
        """Start the crawler."""
        pass

    @abstractmethod
    async def search(self):
        """Run the search flow."""
        pass

    @abstractmethod
    async def launch_browser(self, chromium: BrowserType, playwright_proxy: Optional[Dict], user_agent: Optional[str], headless: bool = True) -> BrowserContext:
        """Launch a browser context."""
        pass

    async def launch_browser_with_cdp(self, playwright: Playwright, playwright_proxy: Optional[Dict], user_agent: Optional[str], headless: bool = True) -> BrowserContext:
        """Launch a browser context through CDP when a crawler supports it."""
        # Default behavior falls back to the regular browser launcher.
        return await self.launch_browser(playwright.chromium, playwright_proxy, user_agent, headless)


class AbstractLogin(ABC):

    @abstractmethod
    async def begin(self):
        pass

    @abstractmethod
    async def login_by_qrcode(self):
        pass

    @abstractmethod
    async def login_by_mobile(self):
        pass

    @abstractmethod
    async def login_by_cookies(self):
        pass


class AbstractStore(ABC):

    @abstractmethod
    async def store_content(self, content_item: Dict):
        pass

    @abstractmethod
    async def store_comment(self, comment_item: Dict):
        pass

    # Not every platform implements creator storage yet.
    @abstractmethod
    async def store_creator(self, creator: Dict):
        pass


class AbstractStoreImage(ABC):
    # Image storage is only implemented for a subset of platforms.
    # @abstractmethod
    async def store_image(self, image_content_item: Dict):
        pass


class AbstractStoreVideo(ABC):
    # Video storage is only implemented for a subset of platforms.
    # @abstractmethod
    async def store_video(self, video_content_item: Dict):
        pass


class AbstractApiClient(ABC):

    @abstractmethod
    async def request(self, method, url, **kwargs):
        pass

    @abstractmethod
    async def update_cookies(self, browser_context: BrowserContext):
        pass
