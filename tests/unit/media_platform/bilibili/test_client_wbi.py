from __future__ import annotations

import asyncio

from media_platform.bilibili.client import BilibiliClient


class _ClosedPage:
    def is_closed(self) -> bool:
        return True

    async def evaluate(self, _script: str):
        raise RuntimeError("should not evaluate closed page")


def test_get_wbi_keys_falls_back_to_nav_api_and_uses_cache() -> None:
    client = BilibiliClient(
        headers={"Cookie": "SESSDATA=fake"},
        playwright_page=_ClosedPage(),  # type: ignore[arg-type]
        cookie_dict={},
    )

    calls = {"count": 0}

    async def _fake_request(*_args, **_kwargs):
        calls["count"] += 1
        return {
            "wbi_img": {
                "img_url": "https://i0.hdslb.com/bfs/wbi/11111111111111111111111111111111.png",
                "sub_url": "https://i0.hdslb.com/bfs/wbi/22222222222222222222222222222222.png",
            }
        }

    client.request = _fake_request  # type: ignore[method-assign]

    img_key, sub_key = asyncio.run(client.get_wbi_keys())
    assert img_key == "11111111111111111111111111111111"
    assert sub_key == "22222222222222222222222222222222"
    assert calls["count"] == 1

    # The second call should hit the in-memory cache and avoid another request.
    img_key_2, sub_key_2 = asyncio.run(client.get_wbi_keys())
    assert (img_key_2, sub_key_2) == (img_key, sub_key)
    assert calls["count"] == 1
