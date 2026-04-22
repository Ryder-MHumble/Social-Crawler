from __future__ import annotations

import pytest

pytest.importorskip("humps")

from media_platform.xhs.extractor import XiaoHongShuExtractor


def test_extract_note_detail_from_html_uses_fallback_key() -> None:
    extractor = XiaoHongShuExtractor()
    html = """
    <html><body>
      <script>
        window.__INITIAL_STATE__={
          "note": {
            "noteDetailMap": {
              "real_note_key": {
                "note": {
                  "noteId": "real_note_key",
                  "title": "test-title",
                  "desc": "test-desc"
                }
              }
            }
          }
        }
      </script>
    </body></html>
    """
    note = extractor.extract_note_detail_from_html("different_id", html)
    assert note is not None
    assert note["note_id"] == "real_note_key"
    assert note["title"] == "test-title"


def test_extract_creator_info_from_html_with_whitespace_script() -> None:
    extractor = XiaoHongShuExtractor()
    html = """
    <html><body>
      <script>
          window.__INITIAL_STATE__ = {
            "user": {
              "userPageData": {
                "basicInfo": {
                  "nickname": "creator-a"
                }
              }
            }
          }
      </script>
    </body></html>
    """
    creator = extractor.extract_creator_info_from_html(html)
    assert creator is not None
    assert creator["basicInfo"]["nickname"] == "creator-a"
