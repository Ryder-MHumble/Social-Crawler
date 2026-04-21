# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/xhs/core.py
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

import asyncio
import json
import os
import random
from asyncio import Task
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)
from tenacity import RetryError

import config
from base.base_crawler import AbstractCrawler
from model.m_xiaohongshu import NoteUrlInfo, CreatorUrlInfo
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import xhs as xhs_store
from tools import runtime_paths, utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import XiaoHongShuClient
from .exception import DataFetchError, NoteNotFoundError
from .field import SearchSortType
from .help import parse_note_info_from_note_url, parse_creator_info_from_url, get_search_id
from .login import XiaoHongShuLogin


class XiaoHongShuCrawler(AbstractCrawler):
    context_page: Page
    xhs_client: XiaoHongShuClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = "https://www.xiaohongshu.com"
        self.user_agent: Optional[str] = None
        self.cdp_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool for automatic proxy refresh

    async def _new_context_page(self) -> Page:
        if self.cdp_manager:
            return await self.cdp_manager.new_page()
        return await self.browser_context.new_page()

    @staticmethod
    def _unwrap_exception_message(exc: BaseException) -> str:
        root: BaseException = exc
        seen: set[int] = set()
        while id(root) not in seen:
            seen.add(id(root))
            nested = getattr(root, "__cause__", None) or getattr(root, "__context__", None)
            if not nested:
                break
            root = nested
        message = str(root).strip() or root.__class__.__name__
        return f"{root.__class__.__name__}: {message}"

    @classmethod
    def _describe_retry_error(cls, retry_error: RetryError) -> str:
        last_attempt = getattr(retry_error, "last_attempt", None)
        attempt_number = getattr(last_attempt, "attempt_number", None)
        prefix = (
            f"retry exhausted after {attempt_number} attempts"
            if attempt_number
            else "retry exhausted"
        )
        if last_attempt is not None:
            try:
                if last_attempt.failed:
                    exception = last_attempt.exception()
                    if exception:
                        return f"{prefix}: {cls._unwrap_exception_message(exception)}"
            except Exception:
                pass
            try:
                result = last_attempt.result()
                return f"{prefix}: last result={result!r}"
            except Exception:
                pass
        return f"{prefix}: {cls._unwrap_exception_message(retry_error)}"

    @staticmethod
    def _normalize_note_candidate(
        post_item: Dict[str, Any],
        default_xsec_source: str = "pc_search",
    ) -> Optional[Dict[str, str]]:
        if not isinstance(post_item, dict):
            return None
        note_card = post_item.get("note_card")
        if not isinstance(note_card, dict):
            note_card = {}
        note_id = str(
            post_item.get("note_id")
            or post_item.get("id")
            or note_card.get("note_id")
            or note_card.get("id")
            or ""
        ).strip()
        if not note_id:
            return None
        return {
            "note_id": note_id,
            "xsec_token": str(post_item.get("xsec_token") or note_card.get("xsec_token") or "").strip(),
            "xsec_source": str(
                post_item.get("xsec_source")
                or note_card.get("xsec_source")
                or default_xsec_source
            ).strip()
            or default_xsec_source,
        }

    @staticmethod
    def _format_accept_language(languages: List[str]) -> str:
        if not languages:
            return "zh-CN,zh;q=0.9"
        normalized: List[str] = []
        seen: set[str] = set()
        for language in languages:
            candidate = str(language or "").strip()
            key = candidate.lower()
            if not candidate or key in seen:
                continue
            seen.add(key)
            normalized.append(candidate)
        if not normalized:
            return "zh-CN,zh;q=0.9"
        values: List[str] = []
        for index, language in enumerate(normalized[:4]):
            if index == 0:
                values.append(language)
            else:
                quality = max(0.1, 1.0 - (index * 0.1))
                values.append(f"{language};q={quality:.1f}")
        return ",".join(values)

    @staticmethod
    def _format_sec_ch_ua(brands: List[Dict[str, Any]]) -> str:
        formatted_brands: List[str] = []
        for brand in brands:
            if not isinstance(brand, dict):
                continue
            name = str(brand.get("brand") or "").strip()
            version = str(brand.get("version") or "").strip()
            if not name or not version:
                continue
            formatted_brands.append(f'"{name}";v="{version}"')
        return ", ".join(formatted_brands)

    async def _get_live_browser_profile(self) -> Dict[str, Any]:
        profile = await self.context_page.evaluate(
            """() => {
                const uaData = navigator.userAgentData || null;
                return {
                    userAgent: navigator.userAgent || "",
                    language: navigator.language || "",
                    languages: Array.isArray(navigator.languages) ? navigator.languages : [],
                    platform: uaData?.platform || navigator.platform || "",
                    mobile: typeof uaData?.mobile === "boolean" ? uaData.mobile : /Mobile/i.test(navigator.userAgent || ""),
                    brands: Array.isArray(uaData?.brands) ? uaData.brands : [],
                };
            }"""
        )
        if not isinstance(profile, dict):
            return {}
        return profile

    async def _build_live_headers(self, cookie_str: str) -> Dict[str, str]:
        profile = await self._get_live_browser_profile()
        languages = profile.get("languages")
        if not isinstance(languages, list):
            languages = []
        primary_language = str(profile.get("language") or "").strip()
        if primary_language:
            languages = [primary_language, *languages]
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": self._format_accept_language(languages),
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": self.index_url,
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": f"{self.index_url}/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": str(profile.get("userAgent") or "").strip() or os.getenv("USER_AGENT", ""),
            "Cookie": cookie_str,
        }
        sec_ch_ua = self._format_sec_ch_ua(profile.get("brands") if isinstance(profile.get("brands"), list) else [])
        if sec_ch_ua:
            headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?1" if bool(profile.get("mobile")) else "?0"
        platform = str(profile.get("platform") or "").strip()
        if platform:
            headers["sec-ch-ua-platform"] = json.dumps(platform)
        return headers

    @staticmethod
    def _should_crawl_official_accounts() -> bool:
        if config.CRAWLER_TYPE == "official_accounts":
            return True
        return config.CRAWLER_TYPE == "search" and bool(
            getattr(config, "ENABLE_OFFICIAL_ACCOUNTS_CRAWL", False)
        )

    def _resolve_official_account_targets(self) -> List[Dict[str, str]]:
        resolved_accounts: List[Dict[str, str]] = []
        accounts = getattr(config, "XHS_OFFICIAL_ACCOUNTS", [])
        if not isinstance(accounts, list):
            return resolved_accounts

        for account in accounts:
            raw_account = account if isinstance(account, dict) else {"user_id": account}
            if not isinstance(raw_account, dict):
                continue
            identifier = str(
                raw_account.get("profile_url")
                or raw_account.get("url")
                or raw_account.get("creator_url")
                or raw_account.get("user_id")
                or raw_account.get("creator_id")
                or ""
            ).strip()
            if not identifier:
                utils.logger.warning(
                    "[XiaoHongShuCrawler.crawl_official_accounts] Skip official account target without identifier"
                )
                continue
            try:
                creator_info = parse_creator_info_from_url(identifier)
            except ValueError as exc:
                utils.logger.warning(
                    "[XiaoHongShuCrawler.crawl_official_accounts] "
                    f"Skip invalid official account target {identifier}: {exc}"
                )
                continue

            user_id = creator_info.user_id
            xsec_token = str(
                raw_account.get("xsec_token")
                or raw_account.get("token")
                or creator_info.xsec_token
                or ""
            ).strip()
            xsec_source = str(
                raw_account.get("xsec_source")
                or raw_account.get("source")
                or creator_info.xsec_source
                or "pc_feed"
            ).strip() or "pc_feed"
            name = str(raw_account.get("name") or raw_account.get("nickname") or user_id).strip() or user_id
            resolved_accounts.append(
                {
                    "user_id": user_id,
                    "name": name,
                    "xsec_token": xsec_token,
                    "xsec_source": xsec_source,
                }
            )
        return resolved_accounts

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Choose launch mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[XiaoHongShuCrawler] Launching browser using CDP mode")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[XiaoHongShuCrawler] Launching browser using standard mode")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.HEADLESS,
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(
                    path=str(runtime_paths.get_repo_path("libs", "stealth.min.js"))
                )

            self.context_page = await self._new_context_page()
            await self.context_page.goto(self.index_url)

            # Create a client to interact with the Xiaohongshu website.
            self.xhs_client = await self.create_xhs_client(httpx_proxy_format)
            if not await self.xhs_client.pong():
                login_obj = XiaoHongShuLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # input your phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.xhs_client.update_cookies(browser_context=self.browser_context)

            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for notes and retrieve their comment information.
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_notes()
            elif config.CRAWLER_TYPE == "creator":
                # Get creator's information and their notes and comments
                await self.get_creators_and_notes()
            elif config.CRAWLER_TYPE == "official_accounts":
                pass  # skip keyword search, only run official accounts below
            else:
                pass

            if self._should_crawl_official_accounts():
                await self.crawl_official_accounts()

            utils.logger.info("[XiaoHongShuCrawler.start] Xhs Crawler finished ...")

    async def search(self) -> None:
        """Search for notes and retrieve their comment information."""
        utils.logger.info("[XiaoHongShuCrawler.search] Begin search Xiaohongshu keywords")
        xhs_limit_count = 20  # Xiaohongshu limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < xhs_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = xhs_limit_count
        start_page = config.START_PAGE
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[XiaoHongShuCrawler.search] Current search keyword: {keyword}")
            page = 1
            search_id = get_search_id()
            while (page - start_page + 1) * xhs_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Skip page {page}")
                    page += 1
                    continue

                try:
                    utils.logger.info(f"[XiaoHongShuCrawler.search] search Xiaohongshu keyword: {keyword}, page: {page}")
                    note_ids: List[str] = []
                    xsec_tokens: List[str] = []
                    notes_res = await self.xhs_client.get_note_by_keyword(
                        keyword=keyword,
                        search_id=search_id,
                        page=page,
                        sort=(SearchSortType(config.SORT_TYPE) if config.SORT_TYPE != "" else SearchSortType.GENERAL),
                    )
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Search notes response: {notes_res}")
                    if not notes_res or not notes_res.get("has_more", False):
                        utils.logger.info("[XiaoHongShuCrawler.search] No more content!")
                        break
                    normalized_candidates = [
                        candidate
                        for post_item in notes_res.get("items", [])
                        if post_item.get("model_type") not in ("rec_query", "hot_query")
                        for candidate in [self._normalize_note_candidate(post_item, default_xsec_source="pc_search")]
                        if candidate
                    ]
                    semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
                    task_list = [
                        self.get_note_detail_async_task(
                            note_id=note_candidate["note_id"],
                            xsec_source=note_candidate["xsec_source"],
                            xsec_token=note_candidate["xsec_token"],
                            semaphore=semaphore,
                            default_xsec_source="pc_search",
                        )
                        for note_candidate in normalized_candidates
                    ]
                    note_details = await asyncio.gather(*task_list)
                    for note_detail in note_details:
                        if note_detail:
                            await xhs_store.update_xhs_note(note_detail)
                            await self.get_notice_media(note_detail)
                            note_ids.append(note_detail.get("note_id"))
                            xsec_tokens.append(note_detail.get("xsec_token"))
                    page += 1
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Note details: {note_details}")
                    await self.batch_get_note_comments(note_ids, xsec_tokens)

                    # Sleep after each page navigation
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                    utils.logger.info(f"[XiaoHongShuCrawler.search] Sleeping for {config.CRAWLER_MAX_SLEEP_SEC} seconds after page {page-1}")
                except DataFetchError:
                    utils.logger.error("[XiaoHongShuCrawler.search] Get note detail error")
                    break

    async def get_creators_and_notes(self) -> None:
        """Get creator's notes and retrieve their comment information."""
        utils.logger.info("[XiaoHongShuCrawler.get_creators_and_notes] Begin get Xiaohongshu creators")
        for creator_url in config.XHS_CREATOR_ID_LIST:
            try:
                # Parse creator URL to get user_id and security tokens
                creator_info: CreatorUrlInfo = parse_creator_info_from_url(creator_url)
                utils.logger.info(f"[XiaoHongShuCrawler.get_creators_and_notes] Parse creator URL info: {creator_info}")
                user_id = creator_info.user_id
                creator_xsec_source = creator_info.xsec_source or "pc_feed"

                # get creator detail info from web html content
                createor_info: Dict = await self.xhs_client.get_creator_info(
                    user_id=user_id,
                    xsec_token=creator_info.xsec_token,
                    xsec_source=creator_xsec_source,
                )
                if createor_info:
                    await xhs_store.save_creator(user_id, creator=createor_info)
            except ValueError as e:
                utils.logger.error(f"[XiaoHongShuCrawler.get_creators_and_notes] Failed to parse creator URL: {e}")
                continue

            # Use fixed crawling interval
            crawl_interval = config.CRAWLER_MAX_SLEEP_SEC
            # Get all note information of the creator
            all_notes_list = await self.xhs_client.get_all_notes_by_creator(
                user_id=user_id,
                crawl_interval=crawl_interval,
                callback=self.fetch_creator_notes_detail,
                xsec_token=creator_info.xsec_token,
                xsec_source=creator_xsec_source,
            )

            note_ids = []
            xsec_tokens = []
            for note_item in all_notes_list:
                note_ids.append(note_item.get("note_id"))
                xsec_tokens.append(note_item.get("xsec_token"))
            await self.batch_get_note_comments(note_ids, xsec_tokens)

    async def crawl_official_accounts(self) -> None:
        """Crawl posts and comments from designated official XHS accounts.

        source_keyword is set to "@{account_name}" so the data can be
        distinguished from keyword-search results in the database.
        """
        accounts = self._resolve_official_account_targets()
        if not accounts:
            return

        utils.logger.info("[XiaoHongShuCrawler.crawl_official_accounts] Begin crawling official accounts")
        for account in accounts:
            user_id = account.get("user_id", "")
            name = account.get("name", user_id)
            xsec_token = account.get("xsec_token", "")
            xsec_source = account.get("xsec_source", "pc_feed")
            if not user_id:
                continue

            utils.logger.info(
                f"[XiaoHongShuCrawler.crawl_official_accounts] Crawling @{name} (user_id={user_id})"
            )
            # Mark source as official account — store/filter layers check this prefix
            source_keyword_var.set(f"@{name}")

            try:
                all_notes_list = await self.xhs_client.get_all_notes_by_creator(
                    user_id=user_id,
                    crawl_interval=float(config.CRAWLER_MAX_SLEEP_SEC),
                    callback=self.fetch_creator_notes_detail,
                    xsec_token=xsec_token,
                    xsec_source=xsec_source,
                )
            except RetryError as ex:
                utils.logger.warning(
                    f"[XiaoHongShuCrawler.crawl_official_accounts] Failed to crawl @{name} ({user_id}), "
                    f"skip this account: {self._describe_retry_error(ex)}"
                )
                continue
            except Exception as ex:
                utils.logger.exception(
                    f"[XiaoHongShuCrawler.crawl_official_accounts] Unexpected error when crawling "
                    f"@{name} ({user_id}), skip this account: {ex}"
                )
                continue

            note_ids = [n.get("note_id") for n in all_notes_list if n.get("note_id")]
            xsec_tokens = [n.get("xsec_token", "") for n in all_notes_list]
            if note_ids:
                await self.batch_get_note_comments(note_ids, xsec_tokens)

        utils.logger.info("[XiaoHongShuCrawler.crawl_official_accounts] Official accounts crawl done")

    async def fetch_creator_notes_detail(self, note_list: List[Dict]):
        """Concurrently obtain the specified post list and save the data"""
        normalized_candidates = [
            candidate
            for post_item in note_list
            for candidate in [self._normalize_note_candidate(post_item, default_xsec_source="pc_feed")]
            if candidate
        ]
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self.get_note_detail_async_task(
                note_id=note_candidate["note_id"],
                xsec_source=note_candidate["xsec_source"],
                xsec_token=note_candidate["xsec_token"],
                semaphore=semaphore,
                default_xsec_source="pc_feed",
            )
            for note_candidate in normalized_candidates
        ]

        note_details = await asyncio.gather(*task_list)
        for note_detail in note_details:
            if note_detail:
                await xhs_store.update_xhs_note(note_detail)
                await self.get_notice_media(note_detail)

    async def get_specified_notes(self):
        """Get the information and comments of the specified post

        Note: Must specify note_id, xsec_source, xsec_token
        """
        get_note_detail_task_list = []
        for full_note_url in config.XHS_SPECIFIED_NOTE_URL_LIST:
            note_url_info: NoteUrlInfo = parse_note_info_from_note_url(full_note_url)
            utils.logger.info(f"[XiaoHongShuCrawler.get_specified_notes] Parse note url info: {note_url_info}")
            crawler_task = self.get_note_detail_async_task(
                note_id=note_url_info.note_id,
                xsec_source=note_url_info.xsec_source,
                xsec_token=note_url_info.xsec_token,
                semaphore=asyncio.Semaphore(config.MAX_CONCURRENCY_NUM),
                default_xsec_source="pc_search",
            )
            get_note_detail_task_list.append(crawler_task)

        need_get_comment_note_ids = []
        xsec_tokens = []
        note_details = await asyncio.gather(*get_note_detail_task_list)
        for note_detail in note_details:
            if note_detail:
                need_get_comment_note_ids.append(note_detail.get("note_id", ""))
                xsec_tokens.append(note_detail.get("xsec_token", ""))
                await xhs_store.update_xhs_note(note_detail)
                await self.get_notice_media(note_detail)
        await self.batch_get_note_comments(need_get_comment_note_ids, xsec_tokens)

    async def get_note_detail_async_task(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
        semaphore: asyncio.Semaphore,
        default_xsec_source: str = "pc_search",
    ) -> Optional[Dict]:
        """Get note detail

        Args:
            note_id:
            xsec_source:
            xsec_token:
            semaphore:

        Returns:
            Dict: note detail
        """
        note_id = str(note_id or "").strip()
        xsec_source = str(xsec_source or "").strip() or default_xsec_source
        xsec_token = str(xsec_token or "").strip()
        note_detail = None
        utils.logger.info(f"[get_note_detail_async_task] Begin get note detail, note_id: {note_id}")
        if not note_id:
            utils.logger.warning("[get_note_detail_async_task] Skip note detail fetch because note_id is empty")
            return None
        async with semaphore:
            try:
                retry_details: List[str] = []
                try:
                    note_detail = await self.xhs_client.get_note_by_id(note_id, xsec_source, xsec_token)
                except RetryError as ex:
                    retry_detail = f"API detail {self._describe_retry_error(ex)}"
                    retry_details.append(retry_detail)
                    utils.logger.warning(
                        f"[get_note_detail_async_task] API detail retry exhausted for note_id:{note_id}, {retry_detail}. "
                        "Falling back to browser-backed extraction."
                    )

                if not note_detail:
                    try:
                        note_detail = await self.xhs_client.get_note_by_id_from_browser(
                            note_id,
                            xsec_source,
                            xsec_token,
                        )
                    except RetryError as ex:
                        retry_detail = f"browser detail {self._describe_retry_error(ex)}"
                        retry_details.append(retry_detail)
                        utils.logger.warning(
                            f"[get_note_detail_async_task] Browser-backed detail retry exhausted for note_id:{note_id}, "
                            f"{retry_detail}. Falling back to raw HTML."
                        )

                if not note_detail:
                    try:
                        note_detail = await self.xhs_client.get_note_by_id_from_html(
                            note_id,
                            xsec_source,
                            xsec_token,
                            enable_cookie=True,
                        )
                    except RetryError as ex:
                        retry_detail = f"HTML detail {self._describe_retry_error(ex)}"
                        retry_details.append(retry_detail)
                        utils.logger.warning(
                            f"[get_note_detail_async_task] Raw HTML detail retry exhausted for note_id:{note_id}, "
                            f"{retry_detail}."
                        )
                    if not note_detail:
                        details_suffix = f" Details: {'; '.join(retry_details)}" if retry_details else ""
                        utils.logger.warning(
                            "[get_note_detail_async_task] Failed to get note detail after API and HTML fallback "
                            f"(browser-backed extraction also failed), skip note_id: {note_id}.{details_suffix}"
                        )
                        return None

                note_detail.update({"xsec_token": xsec_token, "xsec_source": xsec_source})

                # Sleep after fetching note detail
                await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                utils.logger.info(f"[get_note_detail_async_task] Sleeping for {config.CRAWLER_MAX_SLEEP_SEC} seconds after fetching note {note_id}")

                return note_detail

            except NoteNotFoundError as ex:
                utils.logger.warning(f"[XiaoHongShuCrawler.get_note_detail_async_task] Note not found: {note_id}, {ex}")
                return None
            except DataFetchError as ex:
                utils.logger.error(f"[XiaoHongShuCrawler.get_note_detail_async_task] Get note detail error: {ex}")
                return None
            except KeyError as ex:
                utils.logger.error(f"[XiaoHongShuCrawler.get_note_detail_async_task] have not fund note detail note_id:{note_id}, err: {ex}")
                return None
            except Exception as ex:
                utils.logger.exception(
                    f"[XiaoHongShuCrawler.get_note_detail_async_task] Unexpected error for note_id:{note_id}, err: {ex}"
                )
                return None

    async def batch_get_note_comments(self, note_list: List[str], xsec_tokens: List[str]):
        """Batch get note comments"""
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(f"[XiaoHongShuCrawler.batch_get_note_comments] Crawling comment mode is not enabled")
            return

        utils.logger.info(f"[XiaoHongShuCrawler.batch_get_note_comments] Begin batch get note comments, note list: {note_list}")
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list: List[Task] = []
        for index, note_id in enumerate(note_list):
            task = asyncio.create_task(
                self.get_comments(note_id=note_id, xsec_token=xsec_tokens[index], semaphore=semaphore),
                name=note_id,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments(self, note_id: str, xsec_token: str, semaphore: asyncio.Semaphore):
        """Get note comments with keyword filtering and quantity limitation"""
        async with semaphore:
            utils.logger.info(f"[XiaoHongShuCrawler.get_comments] Begin get note id comments {note_id}")
            # Use fixed crawling interval
            crawl_interval = config.CRAWLER_MAX_SLEEP_SEC
            await self.xhs_client.get_note_all_comments(
                note_id=note_id,
                xsec_token=xsec_token,
                crawl_interval=crawl_interval,
                callback=xhs_store.batch_update_xhs_note_comments,
                max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
            )

            # Sleep after fetching comments
            await asyncio.sleep(crawl_interval)
            utils.logger.info(f"[XiaoHongShuCrawler.get_comments] Sleeping for {crawl_interval} seconds after fetching comments for note {note_id}")

    async def create_xhs_client(self, httpx_proxy: Optional[str]) -> XiaoHongShuClient:
        """Create Xiaohongshu client"""
        utils.logger.info("[XiaoHongShuCrawler.create_xhs_client] Begin create Xiaohongshu API client ...")
        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())
        live_headers = await self._build_live_headers(cookie_str)
        xhs_client_obj = XiaoHongShuClient(
            proxy=httpx_proxy,
            headers=live_headers,
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
            page_factory=self._new_context_page,
            proxy_ip_pool=self.ip_proxy_pool,  # Pass proxy pool for automatic refresh
        )
        return xhs_client_obj

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser and create browser context"""
        utils.logger.info("[XiaoHongShuCrawler.launch_browser] Begin create browser context ...")
        if config.SAVE_LOGIN_STATE:
            # feat issue #14
            # we will save login state to avoid login every time
            runtime_paths.ensure_runtime_layout()
            user_data_dir = str(
                runtime_paths.get_browser_user_data_dir(config.PLATFORM, config.USER_DATA_DIR)
            )
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,  # type: ignore
                channel="chrome",  # Use system Chrome stable version
                viewport={
                    "width": 1920,
                    "height": 1080
                },
                user_agent=user_agent,
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy, channel="chrome")  # type: ignore
            browser_context = await browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=user_agent)
            return browser_context

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser using CDP mode"""
        try:
            self.cdp_manager = CDPBrowserManager()
            browser_context = await self.cdp_manager.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )

            # Display browser information
            browser_info = await self.cdp_manager.get_browser_info()
            utils.logger.info(f"[XiaoHongShuCrawler] CDP browser info: {browser_info}")

            return browser_context

        except Exception as e:
            utils.logger.error(f"[XiaoHongShuCrawler] CDP mode launch failed, falling back to standard mode: {e}")
            # Fall back to standard mode
            chromium = playwright.chromium
            return await self.launch_browser(chromium, playwright_proxy, user_agent, headless)

    async def close(self):
        """Close browser context"""
        # Special handling if using CDP mode
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
            self.cdp_manager = None
        else:
            await self.browser_context.close()
        utils.logger.info("[XiaoHongShuCrawler.close] Browser context closed ...")

    async def get_notice_media(self, note_detail: Dict):
        if not config.ENABLE_GET_MEIDAS:
            utils.logger.info(f"[XiaoHongShuCrawler.get_notice_media] Crawling image mode is not enabled")
            return
        await self.get_note_images(note_detail)
        await self.get_notice_video(note_detail)

    async def get_note_images(self, note_item: Dict):
        """Get note images. Please use get_notice_media

        Args:
            note_item: Note item dictionary
        """
        if not config.ENABLE_GET_MEIDAS:
            return
        note_id = note_item.get("note_id")
        image_list: List[Dict] = note_item.get("image_list", [])

        for img in image_list:
            if img.get("url_default") != "":
                img.update({"url": img.get("url_default")})

        if not image_list:
            return
        picNum = 0
        for pic in image_list:
            url = pic.get("url")
            if not url:
                continue
            content = await self.xhs_client.get_note_media(url)
            await asyncio.sleep(random.random())
            if content is None:
                continue
            extension_file_name = f"{picNum}.jpg"
            picNum += 1
            await xhs_store.update_xhs_note_image(note_id, content, extension_file_name)

    async def get_notice_video(self, note_item: Dict):
        """Get note videos. Please use get_notice_media

        Args:
            note_item: Note item dictionary
        """
        if not config.ENABLE_GET_MEIDAS:
            return
        note_id = note_item.get("note_id")

        videos = xhs_store.get_video_url_arr(note_item)

        if not videos:
            return
        videoNum = 0
        for url in videos:
            content = await self.xhs_client.get_note_media(url)
            await asyncio.sleep(random.random())
            if content is None:
                continue
            extension_file_name = f"{videoNum}.mp4"
            videoNum += 1
            await xhs_store.update_xhs_note_video(note_id, content, extension_file_name)
