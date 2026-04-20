# -*- coding: utf-8 -*-
"""Reusable relevance matching helpers for cleaned content filtering."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

_SEPARATOR_PATTERN = re.compile(r"[\s\-_./\\|,，。！？!?:：;；、()\[\]{}<>《》\"'`~@#%^&*+=]+")
_ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")


def _as_keyword_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable):
        items: list[str] = []
        for raw in value:
            text = str(raw).strip()
            if text:
                items.append(text)
        return items
    text = str(value).strip()
    return [text] if text else []


def _normalize_text(value: str) -> str:
    return _SEPARATOR_PATTERN.sub("", (value or "").lower().strip())


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _longest_common_substring_len(left: str, right: str) -> int:
    if not left or not right:
        return 0
    prev = [0] * (len(right) + 1)
    best = 0
    for left_char in left:
        curr = [0] * (len(right) + 1)
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                curr[index] = prev[index - 1] + 1
                if curr[index] > best:
                    best = curr[index]
        prev = curr
    return best


def _keyword_match_loose(
    *,
    keyword: str,
    normalized_text: str,
    min_match_chars: int,
    min_match_ratio: float,
) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return False

    if normalized_keyword in normalized_text:
        return True

    # English identifiers often appear as one token in source keywords
    # but as split words in content text (e.g. zhongguancun_ai_research).
    for token in _ASCII_TOKEN_PATTERN.findall(keyword.lower()):
        if token in normalized_text:
            return True

    # Fallback for Chinese / mixed text: allow partial contiguous overlap.
    # This is intentionally looser than exact phrase matching.
    if len(normalized_keyword) <= 3:
        return False
    overlap = _longest_common_substring_len(normalized_keyword, normalized_text)
    required = max(min_match_chars, math.ceil(len(normalized_keyword) * min_match_ratio))
    required = min(required, len(normalized_keyword))
    return overlap >= required


def is_content_relevant(
    *,
    title: str,
    description: str,
    must_contain: object,
    exclude_keywords: object,
    match_mode: str = "loose",
    min_match_chars: int = 3,
    min_match_ratio: float = 0.3,
) -> bool:
    text = _normalize_text(f"{title or ''} {description or ''}")

    excludes = _as_keyword_list(exclude_keywords)
    for keyword in excludes:
        normalized = _normalize_text(keyword)
        if normalized and normalized in text:
            return False

    required_keywords = _as_keyword_list(must_contain)
    if not required_keywords:
        return True

    mode = str(match_mode or "loose").strip().lower()
    if mode not in {"strict", "loose"}:
        mode = "loose"

    min_chars = max(2, _coerce_int(min_match_chars, 3))
    ratio = _coerce_float(min_match_ratio, 0.3)
    ratio = max(0.1, min(ratio, 1.0))

    if mode == "strict":
        return any(
            _normalize_text(keyword) and _normalize_text(keyword) in text
            for keyword in required_keywords
        )

    return any(
        _keyword_match_loose(
            keyword=keyword,
            normalized_text=text,
            min_match_chars=min_chars,
            min_match_ratio=ratio,
        )
        for keyword in required_keywords
    )
