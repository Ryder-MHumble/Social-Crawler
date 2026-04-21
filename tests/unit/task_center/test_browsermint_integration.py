from __future__ import annotations

import pytest
from playwright.sync_api import Error as PlaywrightError

from api.services.browsermint_integration import (
    BrowsermintProbeFailed,
    BrowsermintSessionConnection,
    _probe_bilibili_login,
    _probe_douyin_login,
    _probe_weibo_login,
    _probe_xhs_login,
    probe_browsermint_login,
)


def _cookie(name: str, value: str = "1") -> dict[str, str]:
    return {"name": name, "value": value}


class DummyResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: dict | None = None,
        text: str = "",
        json_exc: Exception | None = None,
    ) -> None:
        self.status = status
        self._payload = payload or {}
        self._text = text
        self._json_exc = json_exc

    def json(self) -> dict:
        if self._json_exc is not None:
            raise self._json_exc
        return dict(self._payload)

    def text(self) -> str:
        return self._text


class DummyRequestContext:
    def __init__(self, *, response: DummyResponse | None = None, exc: Exception | None = None) -> None:
        self.response = response or DummyResponse()
        self.exc = exc
        self.calls: list[tuple[str, dict, int, bool]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: int, fail_on_status_code: bool) -> DummyResponse:
        self.calls.append((url, dict(headers), timeout, fail_on_status_code))
        if self.exc is not None:
            raise self.exc
        return self.response


class DummyContext:
    def __init__(
        self,
        *,
        cookies: list[dict[str, str]],
        request_context: DummyRequestContext | None = None,
    ) -> None:
        self._cookies = list(cookies)
        self.request = request_context or DummyRequestContext()
        self.new_page_calls = 0

    def cookies(self, urls=None) -> list[dict[str, str]]:
        return list(self._cookies)

    def new_page(self):
        self.new_page_calls += 1
        raise AssertionError("Bilibili preflight should not create a visible page")


def test_probe_bilibili_login_requires_login_cookies() -> None:
    context = DummyContext(cookies=[_cookie("_uuid"), _cookie("buvid3")])

    ok, reason = _probe_bilibili_login(context)

    assert ok is False
    assert "SESSDATA / DedeUserID" in reason
    assert context.new_page_calls == 0
    assert context.request.calls == []


def test_probe_bilibili_login_uses_browser_context_nav_probe() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "code": 0,
                "data": {"isLogin": True},
            },
        ),
    )
    context = DummyContext(
        cookies=[_cookie("SESSDATA"), _cookie("DedeUserID")],
        request_context=request_context,
    )

    ok, reason = _probe_bilibili_login(context)

    assert ok is True
    assert reason == ""
    assert request_context.calls == [
        (
            "https://api.bilibili.com/x/web-interface/nav",
            {
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com/",
            },
            15000,
            False,
        )
    ]
    assert context.new_page_calls == 0


def test_probe_bilibili_login_reports_confirmed_unauthenticated() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "code": -101,
                "message": "账号未登录",
                "data": {"isLogin": False},
            },
        ),
    )
    context = DummyContext(cookies=[_cookie("SESSDATA")], request_context=request_context)

    ok, reason = _probe_bilibili_login(context)

    assert ok is False
    assert "code=-101" in reason
    assert "账号未登录" in reason
    assert context.new_page_calls == 0


def test_probe_bilibili_login_reports_confirmed_unauthenticated_when_code_zero() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "code": 0,
                "message": "0",
                "data": {"isLogin": False},
            },
        ),
    )
    context = DummyContext(cookies=[_cookie("SESSDATA")], request_context=request_context)

    ok, reason = _probe_bilibili_login(context)

    assert ok is False
    assert "账号接口确认未登录" in reason
    assert context.new_page_calls == 0


def test_probe_bilibili_login_raises_probe_failed_when_response_looks_like_risk_block() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "code": -352,
                "message": "风控校验失败",
                "data": {"isLogin": False},
            },
        ),
    )
    context = DummyContext(cookies=[_cookie("SESSDATA")], request_context=request_context)

    with pytest.raises(BrowsermintProbeFailed, match="Bilibili 预检探测失败"):
        _probe_bilibili_login(context)

    assert context.new_page_calls == 0


def test_probe_bilibili_login_raises_probe_failed_on_request_error() -> None:
    request_context = DummyRequestContext(exc=PlaywrightError("network down"))
    context = DummyContext(cookies=[_cookie("SESSDATA")], request_context=request_context)

    with pytest.raises(BrowsermintProbeFailed, match="Bilibili 预检探测失败"):
        _probe_bilibili_login(context)

    assert context.new_page_calls == 0


def test_probe_xhs_login_requires_key_cookies() -> None:
    context = DummyContext(cookies=[_cookie("a1")])

    ok, reason = _probe_xhs_login(context)

    assert ok is False
    assert "web_session / a1" in reason
    assert context.new_page_calls == 0
    assert context.request.calls == []


def test_probe_xhs_login_cookie_only_success() -> None:
    context = DummyContext(cookies=[_cookie("web_session"), _cookie("a1")])

    ok, reason = _probe_xhs_login(context)

    assert ok is True
    assert reason == ""
    assert context.new_page_calls == 0
    assert context.request.calls == []


def test_probe_douyin_login_requires_login_status_cookie() -> None:
    context = DummyContext(cookies=[_cookie("sessionid_ss")])

    ok, reason = _probe_douyin_login(context)

    assert ok is False
    assert "LOGIN_STATUS=1" in reason
    assert context.new_page_calls == 0
    assert context.request.calls == []


def test_probe_douyin_login_reports_unauthenticated_from_api() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "status_code": 8,
                "status_msg": "用户未登录",
                "user": None,
            },
        )
    )
    context = DummyContext(cookies=[_cookie("LOGIN_STATUS", "1")], request_context=request_context)

    ok, reason = _probe_douyin_login(context)

    assert ok is False
    assert "Douyin 账号接口返回未登录" in reason
    assert context.new_page_calls == 0


def test_probe_douyin_login_falls_back_to_cookie_when_probe_inconclusive() -> None:
    request_context = DummyRequestContext(exc=PlaywrightError("network down"))
    context = DummyContext(cookies=[_cookie("LOGIN_STATUS", "1")], request_context=request_context)

    ok, reason = _probe_douyin_login(context)

    assert ok is True
    assert reason == ""
    assert context.new_page_calls == 0


def test_probe_weibo_login_reports_unauthenticated_from_api() -> None:
    request_context = DummyRequestContext(
        response=DummyResponse(
            status=200,
            payload={
                "ok": 1,
                "data": {
                    "login": False,
                },
            },
        )
    )
    context = DummyContext(cookies=[_cookie("WBPSESS")], request_context=request_context)

    ok, reason = _probe_weibo_login(context)

    assert ok is False
    assert "Weibo 配置接口返回未登录" in reason
    assert context.new_page_calls == 0


def test_probe_weibo_login_falls_back_to_cookie_when_probe_inconclusive() -> None:
    request_context = DummyRequestContext(exc=PlaywrightError("network down"))
    context = DummyContext(cookies=[_cookie("SSOLoginState")], request_context=request_context)

    ok, reason = _probe_weibo_login(context)

    assert ok is True
    assert reason == ""
    assert context.new_page_calls == 0


def test_probe_browsermint_login_skips_unsupported_platforms_without_blocking() -> None:
    result = probe_browsermint_login(
        BrowsermintSessionConnection(
            session_id="session-1",
            name="session-1",
            status="running",
            last_active_at=None,
            deep_link_url="",
            expires_at=None,
            cdp_ws_url="ws://example.invalid",
        ),
        {"platforms": ["zhihu", "tieba"]},
    )

    assert result["skipped_platforms"] == ["zhihu", "tieba"]
