# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/xhs/extractor.py
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

import json
import re
from typing import Dict, Optional

import humps


class XiaoHongShuExtractor:
    def __init__(self):
        pass

    @staticmethod
    def _extract_initial_state(html: str) -> Optional[Dict]:
        # Match both `<script>window.__INITIAL_STATE__=...</script>` and variants with whitespace/newlines.
        patterns = (
            r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*<\/script>",
            r"<script>\s*window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*<\/script>",
        )
        state_raw = ""
        for pattern in patterns:
            match = re.search(pattern, html, re.S)
            if match:
                state_raw = match.group(1)
                break
        if not state_raw:
            return None

        # The initial-state payload occasionally contains JS `undefined`.
        normalized_state = state_raw.replace(":undefined", ":null").replace("undefined", "null")
        try:
            return json.loads(normalized_state, strict=False)
        except json.JSONDecodeError:
            return None

    def extract_note_detail_from_html(self, note_id: str, html: str) -> Optional[Dict]:
        """Extract note details from HTML

        Args:
            html (str): HTML string

        Returns:
            Dict: Note details dictionary
        """
        if "noteDetailMap" not in html:
            # Either a CAPTCHA appeared or the note doesn't exist
            return None
        state_obj = self._extract_initial_state(html)
        if not state_obj:
            return None
        note_dict = humps.decamelize(state_obj)
        note_map = note_dict.get("note", {}).get("note_detail_map", {})
        if not isinstance(note_map, dict) or not note_map:
            return None

        # Prefer exact note_id, then fallback to the first map item if key format changed.
        if note_id in note_map:
            return note_map.get(note_id, {}).get("note")
        for _, item in note_map.items():
            note = item.get("note") if isinstance(item, dict) else None
            if note:
                return note
        return None

    def extract_creator_info_from_html(self, html: str) -> Optional[Dict]:
        """Extract user information from HTML

        Args:
            html (str): HTML string

        Returns:
            Dict: User information dictionary
        """
        info = self._extract_initial_state(html)
        if info is None:
            return None
        user_obj = info.get("user") if isinstance(info, dict) else None
        if not isinstance(user_obj, dict):
            return None
        return user_obj.get("userPageData")
