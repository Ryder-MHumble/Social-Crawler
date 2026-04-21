# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/cdp_browser.py
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
import atexit
import os
import signal
import socket
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from playwright.async_api import Browser, BrowserContext, Page, Playwright

import config
from tools.browser_launcher import BrowserLauncher
from tools import runtime_paths, utils


class CDPBrowserManager:
    """
    CDP browser manager, responsible for launching and managing browsers connected via CDP
    """

    def __init__(self):
        self.launcher = BrowserLauncher()
        self.browser: Optional[Browser] = None
        self.browser_context: Optional[BrowserContext] = None
        self.debug_port: Optional[int] = None
        self._cleanup_registered = False
        self._remote_mode: bool = False
        self._owns_remote_context: bool = False
        self._remote_initial_page_guids: set[str] = set()
        self._managed_page_guids: set[str] = set()

    def _register_cleanup_handlers(self):
        """
        Register cleanup handlers to ensure browser process cleanup on program exit
        """
        if self._cleanup_registered:
            return

        def sync_cleanup():
            """Synchronous cleanup function for atexit"""
            if self.launcher and self.launcher.browser_process:
                utils.logger.info("[CDPBrowserManager] atexit: Cleaning up browser process")
                self.launcher.cleanup()

        # Register atexit cleanup
        atexit.register(sync_cleanup)

        # Register signal handlers (only when no custom handlers exist, to avoid overriding main entry signal handling logic)
        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)

        def signal_handler(signum, frame):
            """Signal handler"""
            utils.logger.info(f"[CDPBrowserManager] Received signal {signum}, cleaning up browser process")
            if self.launcher and self.launcher.browser_process:
                self.launcher.cleanup()

            if signum == signal.SIGINT:
                if prev_sigint == signal.default_int_handler:
                    return prev_sigint(signum, frame)
                raise KeyboardInterrupt

            raise SystemExit(0)

        install_sigint = prev_sigint in (signal.default_int_handler, signal.SIG_DFL)
        install_sigterm = prev_sigterm == signal.SIG_DFL

        # Register SIGINT (Ctrl+C) and SIGTERM
        if install_sigint:
            signal.signal(signal.SIGINT, signal_handler)
        else:
            utils.logger.info("[CDPBrowserManager] SIGINT handler already exists, skipping registration to avoid override")

        if install_sigterm:
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            utils.logger.info("[CDPBrowserManager] SIGTERM handler already exists, skipping registration to avoid override")

        self._cleanup_registered = True
        utils.logger.info("[CDPBrowserManager] Cleanup handlers registered")

    async def launch_and_connect(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = False,
    ) -> BrowserContext:
        """
        Launch browser and connect via CDP. When ``config.CDP_REMOTE_WS_URL`` is set,
        skip the local launch flow and connect to a remote browser directly.
        """
        try:
            self._owns_remote_context = False
            self._remote_initial_page_guids = set()
            self._managed_page_guids = set()
            remote_ws_url = (getattr(config, "CDP_REMOTE_WS_URL", "") or "").strip()
            if remote_ws_url:
                self._remote_mode = True
                await self._connect_remote(playwright, remote_ws_url)
            else:
                self._remote_mode = False
                # 1. Detect browser path
                browser_path = await self._get_browser_path()

                # 2. Get available port
                self.debug_port = self.launcher.find_available_port(config.CDP_DEBUG_PORT)

                # 3. Launch browser
                await self._launch_browser(browser_path, headless)

                # 4. Register cleanup handlers (ensure cleanup on abnormal exit)
                self._register_cleanup_handlers()

                # 5. Connect via CDP
                await self._connect_via_cdp(playwright)

            # 6. Create browser context
            browser_context = await self._create_browser_context(
                playwright_proxy, user_agent
            )

            self.browser_context = browser_context
            return browser_context

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] CDP browser launch failed: {e}")
            await self.cleanup()
            raise

    async def _connect_remote(self, playwright: Playwright, ws_url: str):
        """Connect to a remote CDP browser endpoint (e.g. hosted browserless)."""
        headers = getattr(config, "CDP_REMOTE_HEADERS", None) or None
        # Mask token in log output so it does not leak into task logs.
        safe_url = ws_url.split("?", 1)[0] + ("?<token hidden>" if "?" in ws_url else "")
        utils.logger.info(f"[CDPBrowserManager] Connecting to remote CDP: {safe_url}")
        self.browser = await playwright.chromium.connect_over_cdp(
            ws_url, headers=headers
        )
        if not self.browser.is_connected():
            raise RuntimeError("Remote CDP connection failed")
        utils.logger.info(
            f"[CDPBrowserManager] Remote CDP connected, contexts={len(self.browser.contexts)}"
        )

    async def _get_browser_path(self) -> str:
        """
        Get browser path
        """
        # Prefer user-defined path
        if config.CUSTOM_BROWSER_PATH and os.path.isfile(config.CUSTOM_BROWSER_PATH):
            utils.logger.info(
                f"[CDPBrowserManager] Using custom browser path: {config.CUSTOM_BROWSER_PATH}"
            )
            return config.CUSTOM_BROWSER_PATH

        # Auto-detect browser path
        browser_paths = self.launcher.detect_browser_paths()

        if not browser_paths:
            raise RuntimeError(
                "No available browser found. Please ensure Chrome or Edge browser is installed, "
                "or set CUSTOM_BROWSER_PATH in config file to specify browser path."
            )

        browser_path = browser_paths[0]  # Use the first browser found
        browser_name, browser_version = self.launcher.get_browser_info(browser_path)

        utils.logger.info(
            f"[CDPBrowserManager] Detected browser: {browser_name} ({browser_version})"
        )
        utils.logger.info(f"[CDPBrowserManager] Browser path: {browser_path}")

        return browser_path

    async def _test_cdp_connection(self, debug_port: int) -> bool:
        """
        Test if CDP connection is available
        """
        try:
            # Simple socket connection test
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(("localhost", debug_port))
                if result == 0:
                    utils.logger.info(
                        f"[CDPBrowserManager] CDP port {debug_port} is accessible"
                    )
                    return True
                else:
                    utils.logger.warning(
                        f"[CDPBrowserManager] CDP port {debug_port} is not accessible"
                    )
                    return False
        except Exception as e:
            utils.logger.warning(f"[CDPBrowserManager] CDP connection test failed: {e}")
            return False

    async def _launch_browser(self, browser_path: str, headless: bool):
        """
        Launch browser process
        """
        # Set user data directory (if save login state is enabled)
        user_data_dir = None
        if config.SAVE_LOGIN_STATE:
            runtime_paths.ensure_runtime_layout()
            user_data_dir = str(
                runtime_paths.get_browser_user_data_dir(
                    config.PLATFORM,
                    config.USER_DATA_DIR,
                    cdp=True,
                )
            )
            os.makedirs(user_data_dir, exist_ok=True)
            utils.logger.info(f"[CDPBrowserManager] User data directory: {user_data_dir}")

        # Launch browser
        self.launcher.browser_process = self.launcher.launch_browser(
            browser_path=browser_path,
            debug_port=self.debug_port,
            headless=headless,
            user_data_dir=user_data_dir,
        )

        # Wait for browser to be ready
        if not self.launcher.wait_for_browser_ready(
            self.debug_port, config.BROWSER_LAUNCH_TIMEOUT
        ):
            raise RuntimeError(f"Browser failed to start within {config.BROWSER_LAUNCH_TIMEOUT} seconds")

        # Extra wait for CDP service to fully start
        await asyncio.sleep(1)

        # Test CDP connection
        if not await self._test_cdp_connection(self.debug_port):
            utils.logger.warning(
                "[CDPBrowserManager] CDP connection test failed, but will continue to try connecting"
            )

    async def _get_browser_websocket_url(self, debug_port: int) -> str:
        """
        Get browser WebSocket connection URL
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{debug_port}/json/version", timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        utils.logger.info(
                            f"[CDPBrowserManager] Got browser WebSocket URL: {ws_url}"
                        )
                        return ws_url
                    else:
                        raise RuntimeError("webSocketDebuggerUrl not found")
                else:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] Failed to get WebSocket URL: {e}")
            raise

    async def _connect_via_cdp(self, playwright: Playwright):
        """
        Connect to browser via CDP
        """
        try:
            # Get correct WebSocket URL
            ws_url = await self._get_browser_websocket_url(self.debug_port)
            utils.logger.info(f"[CDPBrowserManager] Connecting to browser via CDP: {ws_url}")

            # Use Playwright's connectOverCDP method to connect
            self.browser = await playwright.chromium.connect_over_cdp(ws_url)

            if self.browser.is_connected():
                utils.logger.info("[CDPBrowserManager] Successfully connected to browser")
                utils.logger.info(
                    f"[CDPBrowserManager] Browser contexts count: {len(self.browser.contexts)}"
                )
            else:
                raise RuntimeError("CDP connection failed")

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] CDP connection failed: {e}")
            raise

    async def _create_browser_context(
        self, playwright_proxy: Optional[Dict] = None, user_agent: Optional[str] = None
    ) -> BrowserContext:
        """
        Create or get browser context
        """
        if not self.browser:
            raise RuntimeError("Browser not connected")

        # Get existing context or create new context
        contexts = self.browser.contexts

        if contexts:
            # Use existing first context
            browser_context = contexts[0]
            if self._remote_mode:
                self._owns_remote_context = False
                self._remote_initial_page_guids = {
                    self._page_guid(page)
                    for page in browser_context.pages
                    if self._page_guid(page)
                }
            utils.logger.info("[CDPBrowserManager] Using existing browser context")
        else:
            # Create new context
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "accept_downloads": True,
            }

            # Set user agent
            if user_agent:
                context_options["user_agent"] = user_agent
                utils.logger.info(f"[CDPBrowserManager] Setting user agent: {user_agent}")

            # Note: Proxy settings may not work in CDP mode since browser is already launched
            if playwright_proxy:
                if self._remote_mode:
                    utils.logger.warning(
                        "[CDPBrowserManager] Proxy settings are ignored in remote CDP mode; "
                        "configure the proxy on the remote browser service instead"
                    )
                else:
                    utils.logger.warning(
                        "[CDPBrowserManager] Warning: Proxy settings may not work in CDP mode, "
                        "recommend configuring system proxy or browser proxy extension before launching browser"
                    )

            browser_context = await self.browser.new_context(**context_options)
            if self._remote_mode:
                self._owns_remote_context = True
                self._remote_initial_page_guids = set()
            utils.logger.info("[CDPBrowserManager] Created new browser context")

        return browser_context

    @staticmethod
    def _page_guid(page) -> str:
        try:
            return str(page._impl_obj._guid)
        except Exception:
            return ""

    def track_page(self, page: Page) -> None:
        page_guid = self._page_guid(page)
        if page_guid:
            self._managed_page_guids.add(page_guid)

    def untrack_page(self, page: Page) -> None:
        page_guid = self._page_guid(page)
        if page_guid:
            self._managed_page_guids.discard(page_guid)

    async def new_page(self) -> Page:
        if not self.browser_context:
            raise RuntimeError("Browser context not initialized")
        page = await self.browser_context.new_page()
        self.track_page(page)
        return page

    async def _cleanup_remote_pages(self):
        if not self.browser_context or not self._managed_page_guids:
            return
        owned_page_guids = set(self._managed_page_guids)
        for page in list(self.browser_context.pages):
            page_guid = self._page_guid(page)
            if not page_guid or page_guid not in owned_page_guids:
                continue
            try:
                await page.close()
                self._managed_page_guids.discard(page_guid)
            except Exception as page_error:
                error_msg = str(page_error).lower()
                if "closed" not in error_msg and "disconnected" not in error_msg:
                    utils.logger.warning(
                        f"[CDPBrowserManager] Failed to close remote crawler page: {page_error}"
                    )

    async def add_stealth_script(self, script_path: str = "libs/stealth.min.js"):
        """
        Add anti-detection script
        """
        candidate = Path(script_path)
        script = candidate if candidate.is_absolute() else runtime_paths.get_repo_path(script_path)
        if self.browser_context and script.exists():
            try:
                await self.browser_context.add_init_script(path=str(script))
                utils.logger.info(
                    f"[CDPBrowserManager] Added anti-detection script: {script}"
                )
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] Failed to add anti-detection script: {e}")

    async def add_cookies(self, cookies: list):
        """
        Add cookies
        """
        if self.browser_context:
            try:
                await self.browser_context.add_cookies(cookies)
                utils.logger.info(f"[CDPBrowserManager] Added {len(cookies)} cookies")
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] Failed to add cookies: {e}")

    async def get_cookies(self) -> list:
        """
        Get current cookies
        """
        if self.browser_context:
            try:
                cookies = await self.browser_context.cookies()
                return cookies
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] Failed to get cookies: {e}")
                return []
        return []

    async def cleanup(self, force: bool = False):
        """
        Cleanup resources

        Args:
            force: Whether to force cleanup browser process (ignoring AUTO_CLOSE_BROWSER config)
        """
        try:
            # Close browser context
            if self.browser_context:
                try:
                    # Check if context is already closed
                    # Try to get page list, if fails means already closed
                    try:
                        pages = self.browser_context.pages
                        if pages is not None:
                            if self._remote_mode and not self._owns_remote_context:
                                await self._cleanup_remote_pages()
                                utils.logger.info("[CDPBrowserManager] Remote crawler pages closed")
                            else:
                                await self.browser_context.close()
                                utils.logger.info("[CDPBrowserManager] Browser context closed")
                    except:
                        utils.logger.debug("[CDPBrowserManager] Browser context already closed")
                except Exception as context_error:
                    # Only log warning if error is not due to already being closed
                    error_msg = str(context_error).lower()
                    if "closed" not in error_msg and "disconnected" not in error_msg:
                        utils.logger.warning(
                            f"[CDPBrowserManager] Failed to close browser context: {context_error}"
                        )
                    else:
                        utils.logger.debug(f"[CDPBrowserManager] Browser context already closed: {context_error}")
                finally:
                    self.browser_context = None
                    self._owns_remote_context = False
                    self._remote_initial_page_guids = set()
                    self._managed_page_guids = set()

            # Disconnect browser
            if self.browser:
                try:
                    # Check if browser is still connected
                    if self.browser.is_connected():
                        await self.browser.close()
                        utils.logger.info("[CDPBrowserManager] Browser connection disconnected")
                    else:
                        utils.logger.debug("[CDPBrowserManager] Browser connection already disconnected")
                except Exception as browser_error:
                    # Only log warning if error is not due to already being closed
                    error_msg = str(browser_error).lower()
                    if "closed" not in error_msg and "disconnected" not in error_msg:
                        utils.logger.warning(
                            f"[CDPBrowserManager] Failed to close browser connection: {browser_error}"
                        )
                    else:
                        utils.logger.debug(f"[CDPBrowserManager] Browser connection already closed: {browser_error}")
                finally:
                    self.browser = None

            # Close browser process
            # Remote mode has no local process — browser.close() above already dropped
            # the connection, and the remote service owns the browser lifecycle.
            if self._remote_mode:
                utils.logger.debug(
                    "[CDPBrowserManager] Remote CDP mode, skipping local process cleanup"
                )
            # force=True means force close, ignoring AUTO_CLOSE_BROWSER config
            # Used for handling abnormal exit or manual cleanup
            elif force or config.AUTO_CLOSE_BROWSER:
                if self.launcher and self.launcher.browser_process:
                    self.launcher.cleanup()
                else:
                    utils.logger.debug("[CDPBrowserManager] No browser process to cleanup")
            else:
                utils.logger.info(
                    "[CDPBrowserManager] Browser process kept running (AUTO_CLOSE_BROWSER=False)"
                )

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] Error during resource cleanup: {e}")

    def is_connected(self) -> bool:
        """
        Check if connected to browser
        """
        return self.browser is not None and self.browser.is_connected()

    async def get_browser_info(self) -> Dict[str, Any]:
        """
        Get browser info
        """
        if not self.browser:
            return {}

        try:
            version = self.browser.version
            contexts_count = len(self.browser.contexts)

            return {
                "version": version,
                "contexts_count": contexts_count,
                "debug_port": self.debug_port,
                "is_connected": self.is_connected(),
            }
        except Exception as e:
            utils.logger.warning(f"[CDPBrowserManager] Failed to get browser info: {e}")
            return {}
