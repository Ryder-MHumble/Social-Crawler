from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
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


class BrowsermintUserActionRequired(RuntimeError):
    """Raised when the remote session exists but still needs user intervention."""


class BrowsermintProbeFailed(RuntimeError):
    """Raised when the remote session exists but probe execution itself is inconclusive."""


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


def _resolve_target_platforms(params: Mapping[str, Any]) -> list[str]:
    raw_platforms = params.get("platforms")
    if isinstance(raw_platforms, list):
        return [str(item).strip() for item in raw_platforms if str(item).strip()]
    single_platform = str(params.get("platform") or "").strip()
    return [single_platform] if single_platform else []


def _xhs_has_login_cookies(context: BrowserContext) -> bool:
    cookies = _cookies_to_map(context.cookies(urls=["https://www.xiaohongshu.com/"]))
    return bool(cookies.get("web_session") and cookies.get("a1"))


def _douyin_has_login_cookies(context: BrowserContext) -> bool:
    cookies = _cookies_to_map(context.cookies(urls=["https://www.douyin.com/"]))
    return str(cookies.get("LOGIN_STATUS") or "").strip() == "1"


def _weibo_has_login_cookies(context: BrowserContext) -> bool:
    cookies = _cookies_to_map(context.cookies(urls=["https://m.weibo.cn/"]))
    return bool(cookies.get("SSOLoginState") or cookies.get("WBPSESS"))


def _brief_playwright_error(exc: Exception) -> str:
    return str(exc).splitlines()[0].strip() or exc.__class__.__name__


def _context_get_json(
    context: BrowserContext,
    *,
    platform_label: str,
    url: str,
    headers: Mapping[str, str] | None = None,
    timeout_ms: int = 15_000,
) -> tuple[dict[str, Any], int, str]:
    try:
        response = context.request.get(
            url,
            headers=dict(headers or {}),
            timeout=timeout_ms,
            fail_on_status_code=False,
        )
    except PlaywrightError as exc:
        raise BrowsermintProbeFailed(
            f"{platform_label} 预检探测失败: {_brief_playwright_error(exc)}"
        ) from exc

    status = int(response.status)
    body_snippet = ""
    try:
        payload = response.json()
    except Exception:
        try:
            body_snippet = response.text().strip()[:240]
        except Exception:
            body_snippet = ""
        details = [f"status={status}"]
        if body_snippet:
            details.append(f"body={body_snippet}")
        raise BrowsermintProbeFailed(
            f"{platform_label} 预检探测失败: {', '.join(details)}."
        ) from None

    try:
        body_snippet = response.text().strip()[:240]
    except Exception:
        body_snippet = ""
    payload = payload if isinstance(payload, dict) else {}
    return payload, status, body_snippet


def _probe_xhs_login(context: BrowserContext) -> tuple[bool, str]:
    if _xhs_has_login_cookies(context):
        return True, ""
    return False, "未检测到 Xiaohongshu 登录 Cookie（缺少 web_session / a1）。"


def _probe_douyin_login(context: BrowserContext) -> tuple[bool, str]:
    if not _douyin_has_login_cookies(context):
        return False, "未检测到 Douyin 登录 Cookie（缺少 LOGIN_STATUS=1）。"

    try:
        payload, _, _ = _context_get_json(
            context,
            platform_label="Douyin",
            url="https://www.douyin.com/aweme/v1/web/user/profile/self/?aid=6383&device_platform=webapp",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.douyin.com",
                "Referer": "https://www.douyin.com/",
            },
        )
    except BrowsermintProbeFailed:
        # Cookie indicates logged-in and lightweight probe is inconclusive.
        return True, ""

    status_code = payload.get("status_code")
    status_msg = str(payload.get("status_msg") or payload.get("message") or "").strip()
    if status_code == 0:
        return True, ""
    if status_code == 8 or "未登录" in status_msg or "会话过期" in status_msg:
        details: list[str] = []
        if status_code not in (None, ""):
            details.append(f"code={status_code}")
        if status_msg:
            details.append(f"message={status_msg}")
        suffix = f"（{', '.join(details)}）" if details else ""
        return False, f"Douyin 账号接口返回未登录{suffix}。"

    payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    description = str(payload_data.get("description") or "").strip()
    error_code = payload_data.get("error_code")
    if error_code == 1 or "未登录" in description or "会话过期" in description:
        details = []
        if error_code not in (None, ""):
            details.append(f"error_code={error_code}")
        if description:
            details.append(f"message={description}")
        suffix = f"（{', '.join(details)}）" if details else ""
        return False, f"Douyin 账号接口返回未登录{suffix}。"

    return True, ""


def _bilibili_has_login_cookies(context: BrowserContext) -> bool:
    cookies = _cookies_to_map(context.cookies(urls=["https://www.bilibili.com/"]))
    return bool(cookies.get("SESSDATA") or cookies.get("DedeUserID"))


def _probe_bilibili_login(context: BrowserContext) -> tuple[bool, str]:
    if not _bilibili_has_login_cookies(context):
        return False, "未检测到 Bilibili 登录 Cookie（缺少 SESSDATA / DedeUserID）。"

    payload, status, body_snippet = _context_get_json(
        context,
        platform_label="Bilibili",
        url="https://api.bilibili.com/x/web-interface/nav",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.bilibili.com",
            "Referer": "https://www.bilibili.com/",
        },
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if payload.get("code") == 0 and bool(data.get("isLogin")):
        return True, ""

    code = payload.get("code")
    message = str(payload.get("message") or payload.get("msg") or "").strip()
    is_login = data.get("isLogin")
    explicit_login_failure = (
        code == -101
        or (code == 0 and is_login is False)
        or (is_login is False and "未登录" in message)
    )
    if explicit_login_failure:
        details: list[str] = []
        if code not in (None, ""):
            details.append(f"code={code}")
        if message:
            details.append(f"message={message}")
        suffix = f"（{', '.join(details)}）" if details else ""
        return False, f"Bilibili 账号接口确认未登录（Cookie 可能已失效，请在 BrowserMint 会话中重新登录）{suffix}。"

    details = [f"status={status}"]
    if code not in (None, ""):
        details.append(f"code={code}")
    if message:
        details.append(f"message={message}")
    if is_login is False:
        details.append("isLogin=false")
    elif body_snippet:
        details.append(f"body={body_snippet}")
    raise BrowsermintProbeFailed(f"Bilibili 预检探测失败: {', '.join(details)}.")


def _probe_weibo_login(context: BrowserContext) -> tuple[bool, str]:
    if not _weibo_has_login_cookies(context):
        return False, "未检测到 Weibo 登录 Cookie（缺少 SSOLoginState / WBPSESS）。"

    try:
        payload, _, _ = _context_get_json(
            context,
            platform_label="Weibo",
            url="https://m.weibo.cn/api/config",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://m.weibo.cn",
                "Referer": "https://m.weibo.cn/",
            },
        )
    except BrowsermintProbeFailed:
        # Cookie indicates logged-in and lightweight probe is inconclusive.
        return True, ""

    payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if payload.get("ok") == 1 and bool(payload_data.get("login")):
        return True, ""
    if payload.get("ok") == 1 and payload_data.get("login") is False:
        return False, "Weibo 配置接口返回未登录。"
    return True, ""


def probe_browsermint_login(
    connection: BrowsermintSessionConnection,
    normalized_params: Mapping[str, Any],
) -> dict[str, Any]:
    target_platforms = _resolve_target_platforms(normalized_params)
    if not target_platforms:
        return {"skipped_platforms": []}

    unsupported_platforms = [
        platform for platform in target_platforms if platform not in _SUPPORTED_LOGIN_PROBE_PLATFORMS
    ]
    probe_platforms = [
        platform for platform in target_platforms if platform in _SUPPORTED_LOGIN_PROBE_PLATFORMS
    ]
    if not probe_platforms:
        return {"skipped_platforms": unsupported_platforms}

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(connection.cdp_ws_url, timeout=30_000)
        owns_context = False
        if browser.contexts:
            context = browser.contexts[0]
        else:
            owns_context = True
            context = browser.new_context(viewport={"width": 1440, "height": 960})

        try:
            for platform in probe_platforms:
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
                    raise BrowsermintUserActionRequired(
                        f"Browsermint 会话未登录 {label}，已中止启动。原因: {reason}"
                    )
        finally:
            if owns_context:
                try:
                    context.close()
                except PlaywrightError:
                    pass
            browser.close()
    return {"skipped_platforms": unsupported_platforms}


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
