from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

_BROWSERMINT_RUNNABLE_STATUSES = {"running", "paused"}
_SUPPORTED_LOGIN_PROBE_PLATFORMS = {"xhs", "dy", "bili", "wb"}
_PLATFORM_LABELS = {
    "xhs": "Xiaohongshu",
    "dy": "Douyin",
    "bili": "Bilibili",
    "wb": "Weibo",
}


@dataclass(slots=True)
class BrowsermintSessionInfo:
    session_id: str
    name: str
    status: str
    last_active_at: str | None
    deep_link_url: str
    expires_at: str | None


@dataclass(slots=True)
class BrowsermintSessionConnection(BrowsermintSessionInfo):
    cdp_ws_url: str


def _normalize_base_url(raw_url: str) -> str:
    return raw_url.rstrip("/")


def _first_non_empty(*values: Any) -> str:
    for value in values:
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    return ""


def _cookies_to_map(cookies: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(cookie.get("name", "")).strip(): str(cookie.get("value", ""))
        for cookie in cookies
        if str(cookie.get("name", "")).strip()
    }


def _cookies_to_header(cookies: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if cookie.get("name")
    )


def _resolve_target_platforms(params: Mapping[str, Any]) -> list[str]:
    raw_platforms = params.get("platforms")
    if isinstance(raw_platforms, list):
        return [str(item).strip() for item in raw_platforms if str(item).strip()]
    single_platform = str(params.get("platform") or "").strip()
    return [single_platform] if single_platform else []


def _ensure_page_closed(page: Page | None) -> None:
    if page is None:
        return
    try:
        page.close()
    except PlaywrightError:
        pass


def _xhs_has_login_cookies(context: BrowserContext) -> bool:
    cookies = _cookies_to_map(context.cookies(urls=["https://www.xiaohongshu.com/"]))
    return bool(cookies.get("web_session") and cookies.get("a1"))


def _brief_playwright_error(exc: Exception) -> str:
    return str(exc).splitlines()[0].strip() or exc.__class__.__name__


def _probe_xhs_login(context: BrowserContext) -> tuple[bool, str]:
    # Prefer cookie check first to avoid rejecting valid sessions because of transient page-load timeouts.
    if _xhs_has_login_cookies(context):
        return True, ""

    page: Page | None = None
    try:
        page = context.new_page()
        try:
            page.goto("https://www.xiaohongshu.com/", wait_until="commit", timeout=15_000)
            page.wait_for_timeout(1_000)
        except PlaywrightTimeoutError:
            if _xhs_has_login_cookies(context):
                return True, ""
            return False, "访问 Xiaohongshu 首页超时，请在 Browsermint 会话里先打开并确认页面可访问。"
        except PlaywrightError as exc:
            if _xhs_has_login_cookies(context):
                return True, ""
            return False, f"打开 Xiaohongshu 失败: {_brief_playwright_error(exc)}"

        try:
            if page.is_visible("a[href*='/user/profile/']", timeout=1_500):
                return True, ""
        except PlaywrightError:
            pass
        if _xhs_has_login_cookies(context):
            return True, ""
        return False, "未检测到 Xiaohongshu 已登录态。"
    finally:
        _ensure_page_closed(page)


def _probe_douyin_login(context: BrowserContext) -> tuple[bool, str]:
    page: Page | None = None
    try:
        page = context.new_page()
        try:
            page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightError as exc:
            cookies = _cookies_to_map(context.cookies(urls=["https://www.douyin.com/"]))
            if cookies.get("LOGIN_STATUS") == "1":
                return True, ""
            return False, f"打开 Douyin 失败: {_brief_playwright_error(exc)}"
        page.wait_for_timeout(1_500)
        try:
            local_storage = page.evaluate("() => ({ ...window.localStorage })") or {}
        except PlaywrightError:
            local_storage = {}
        cookies = _cookies_to_map(context.cookies(urls=["https://www.douyin.com/"]))
        if str(local_storage.get("HasUserLogin", "")) == "1" or cookies.get("LOGIN_STATUS") == "1":
            return True, ""
        return False, "未检测到 Douyin 已登录态。"
    finally:
        _ensure_page_closed(page)


def _probe_bilibili_login(context: BrowserContext) -> tuple[bool, str]:
    page: Page | None = None
    try:
        page = context.new_page()
        try:
            page.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightError as exc:
            return False, f"打开 Bilibili 失败: {_brief_playwright_error(exc)}"
        page.wait_for_timeout(1_200)
        user_agent = str(page.evaluate("() => navigator.userAgent"))
        cookies = context.cookies(urls=["https://www.bilibili.com/"])
        cookie_header = _cookies_to_header(cookies)
        if not cookie_header:
            return False, "未检测到 Bilibili 登录 Cookie。"
        response = httpx.get(
            "https://api.bilibili.com/x/web-interface/nav",
            headers={
                "User-Agent": user_agent,
                "Cookie": cookie_header,
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") == 0 and bool(payload.get("data", {}).get("isLogin")):
            return True, ""
        return False, "Bilibili 导航接口返回未登录。"
    except httpx.HTTPError as exc:
        return False, f"Bilibili 登录探测请求失败: {exc.__class__.__name__}"
    finally:
        _ensure_page_closed(page)


def _probe_weibo_login(context: BrowserContext) -> tuple[bool, str]:
    page: Page | None = None
    try:
        page = context.new_page()
        try:
            page.goto("https://m.weibo.cn/", wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightError as exc:
            return False, f"打开 Weibo 失败: {_brief_playwright_error(exc)}"
        page.wait_for_timeout(1_200)
        user_agent = str(page.evaluate("() => navigator.userAgent"))
        cookies = context.cookies(urls=["https://m.weibo.cn/"])
        cookie_header = _cookies_to_header(cookies)
        if not cookie_header:
            return False, "未检测到 Weibo 登录 Cookie。"
        response = httpx.get(
            "https://m.weibo.cn/api/config",
            headers={
                "User-Agent": user_agent,
                "Cookie": cookie_header,
                "Origin": "https://m.weibo.cn",
                "Referer": "https://m.weibo.cn",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") == 1 and bool(payload.get("data", {}).get("login")):
            return True, ""
        return False, "Weibo 配置接口返回未登录。"
    except httpx.HTTPError as exc:
        return False, f"Weibo 登录探测请求失败: {exc.__class__.__name__}"
    finally:
        _ensure_page_closed(page)


def probe_browsermint_login(
    connection: BrowsermintSessionConnection,
    normalized_params: Mapping[str, Any],
) -> None:
    target_platforms = _resolve_target_platforms(normalized_params)
    unsupported_platforms = [
        platform for platform in target_platforms if platform not in _SUPPORTED_LOGIN_PROBE_PLATFORMS
    ]
    if unsupported_platforms:
        labels = ", ".join(_PLATFORM_LABELS.get(platform, platform) for platform in unsupported_platforms)
        raise RuntimeError(f"Browsermint 登录预检暂不支持这些平台: {labels}")

    if not target_platforms:
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(connection.cdp_ws_url, timeout=30_000)
        owns_context = False
        if browser.contexts:
            context = browser.contexts[0]
        else:
            owns_context = True
            context = browser.new_context(viewport={"width": 1440, "height": 960})

        try:
            for platform in target_platforms:
                if platform == "xhs":
                    ok, reason = _probe_xhs_login(context)
                elif platform == "dy":
                    ok, reason = _probe_douyin_login(context)
                elif platform == "bili":
                    ok, reason = _probe_bilibili_login(context)
                else:
                    ok, reason = _probe_weibo_login(context)
                if not ok:
                    label = _PLATFORM_LABELS.get(platform, platform)
                    raise RuntimeError(
                        f"Browsermint 会话未登录 {label}，已中止启动。原因: {reason}"
                    )
        finally:
            if owns_context:
                try:
                    context.close()
                except PlaywrightError:
                    pass
            browser.close()


class BrowsermintIntegrationClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        integration_api_key: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(
            base_url or os.getenv("BROWSERMINT_BASE_URL", "").strip()
        )
        self.integration_api_key = (
            integration_api_key
            or os.getenv("BROWSERMINT_INTEGRATION_API_KEY", "").strip()
        )
        self.timeout_sec = float(
            timeout_sec or os.getenv("BROWSERMINT_TIMEOUT_SEC", "15").strip() or 15
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.integration_api_key)

    def list_sessions(self) -> list[BrowsermintSessionInfo]:
        if not self.configured:
            return []
        payload = self._request("GET", "/sessions")
        sessions: list[BrowsermintSessionInfo] = []
        for item in payload.get("sessions", []):
            sessions.append(self._parse_session_info(item))
        return sessions

    def connect_session(self, session_id: str) -> BrowsermintSessionConnection:
        if not self.configured:
            raise RuntimeError("Browsermint integration is not configured.")
        clean_session_id = str(session_id).strip()
        if not clean_session_id:
            raise ValueError("browser_session_id is required when browser_provider=browsermint.")
        payload = self._request("POST", f"/sessions/{clean_session_id}/connect")
        session_payload = payload.get("session", payload)
        connection = self._parse_session_connection(session_payload)
        if connection.status not in _BROWSERMINT_RUNNABLE_STATUSES:
            raise RuntimeError(
                f"Browsermint 会话状态不可用: {connection.status}. 仅支持 running 或 paused。"
            )
        return connection

    def _request(self, method: str, path: str) -> dict[str, Any]:
        headers = {
            "x-integration-api-key": self.integration_api_key,
            "accept": "application/json",
        }
        request_path = path.lstrip("/")
        request_kwargs: dict[str, Any] = {}
        if method.upper() in {"POST", "PUT", "PATCH"}:
            request_kwargs["json"] = {}
        with httpx.Client(
            base_url=f"{self.base_url}/api/integration/",
            timeout=self.timeout_sec,
            headers=headers,
        ) as client:
            response = client.request(method, request_path, **request_kwargs)

        if response.is_success:
            return response.json()

        detail = response.text
        try:
            payload = response.json()
            detail = str(
                payload.get("detail")
                or payload.get("error")
                or payload.get("message")
                or detail
            )
        except ValueError:
            pass
        raise RuntimeError(
            f"Browsermint integration request failed ({response.status_code}): {detail}"
        )

    @staticmethod
    def _parse_session_info(payload: Mapping[str, Any]) -> BrowsermintSessionInfo:
        return BrowsermintSessionInfo(
            session_id=_first_non_empty(payload.get("session_id")),
            name=_first_non_empty(payload.get("name"), payload.get("session_id")),
            status=_first_non_empty(payload.get("status")),
            last_active_at=_first_non_empty(payload.get("lastActiveAt")) or None,
            deep_link_url=_first_non_empty(payload.get("deep_link_url")),
            expires_at=_first_non_empty(payload.get("expires_at")) or None,
        )

    @classmethod
    def _parse_session_connection(
        cls,
        payload: Mapping[str, Any],
    ) -> BrowsermintSessionConnection:
        session_info = cls._parse_session_info(payload)
        cdp_ws_url = _first_non_empty(payload.get("cdp_ws_url"))
        if not cdp_ws_url:
            raise RuntimeError("Browsermint connect response is missing cdp_ws_url.")
        return BrowsermintSessionConnection(
            session_id=session_info.session_id,
            name=session_info.name,
            status=session_info.status,
            last_active_at=session_info.last_active_at,
            deep_link_url=session_info.deep_link_url,
            expires_at=session_info.expires_at,
            cdp_ws_url=cdp_ws_url,
        )
