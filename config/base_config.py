# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/base_config.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台使用条款与 robots 规则。
# 3. 不得进行大规模抓取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要负担。
# 5. 不得用于任何非法或不当用途。

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        return list(default)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _env_json_list(name: str, default: list) -> list:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    try:
        value = json.loads(raw)
    except ValueError:
        return list(default)
    return value if isinstance(value, list) else list(default)


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RUNTIME_DIR = os.getenv("SOCIAL_CRAWLER_RUNTIME_DIR", str(_PROJECT_ROOT / "runtime"))
_DEFAULT_DATA_DIR = os.getenv("SOCIAL_CRAWLER_DATA_DIR", str(Path(_DEFAULT_RUNTIME_DIR) / "data"))

# Basic configuration
PLATFORM = os.getenv("PLATFORM", "xhs")  # xhs | dy | ks | bili | wb | tieba | zhihu
KEYWORDS = os.getenv("KEYWORDS", "编程副业,编程兼职")  # Multiple keywords separated by comma

# ==================== Content Relevance Filter ====================
# Enable to keep only content related to your target entities.
# In search mode this helps remove fuzzy-match noise from platform search results.
ENABLE_RELEVANCE_FILTER = _env_bool("ENABLE_RELEVANCE_FILTER", True)

# Content must contain at least one keyword in title/description.
# You can override this list via env:
# RELEVANCE_MUST_CONTAIN="北京中关村学院,中关村学院,中关村人工智能研究院"
RELEVANCE_MUST_CONTAIN = _env_csv(
    "RELEVANCE_MUST_CONTAIN",
    [
        "北京中关村学院",
        "中关村学院",
        "中关村人工智能研究院",
        "深圳河套",
        "上海创智"
    ],
)

# Exclude content containing any keyword below.
# Optional env override:
# RELEVANCE_EXCLUDE_KEYWORDS="招聘,广告,引流,抽奖"
RELEVANCE_EXCLUDE_KEYWORDS: list[str] = _env_csv("RELEVANCE_EXCLUDE_KEYWORDS", [])

# Relevance matching mode:
# - strict: keyword must be fully contained in title/description
# - loose : allow partial contiguous overlap (more tolerant to fuzzy platform text)
RELEVANCE_MATCH_MODE = os.getenv("RELEVANCE_MATCH_MODE", "loose").strip().lower()
if RELEVANCE_MATCH_MODE not in {"strict", "loose"}:
    RELEVANCE_MATCH_MODE = "loose"

# Loose mode thresholds
RELEVANCE_MIN_MATCH_CHARS = max(2, _env_int("RELEVANCE_MIN_MATCH_CHARS", 3))
RELEVANCE_MIN_MATCH_RATIO = _env_float("RELEVANCE_MIN_MATCH_RATIO", 0.3)
RELEVANCE_MIN_MATCH_RATIO = min(1.0, max(0.1, RELEVANCE_MIN_MATCH_RATIO))

# Minimum engagement (liked_count + comment_count). 0 disables this rule.
MIN_CONTENT_ENGAGEMENT = max(0, _env_int("MIN_CONTENT_ENGAGEMENT", 0))

# Minimum comment length. 0 disables this rule.
MIN_COMMENT_LENGTH = max(0, _env_int("MIN_COMMENT_LENGTH", 5))

# ==================== Official Accounts ====================
# Whether to crawl specified official accounts in addition to keyword search.
ENABLE_OFFICIAL_ACCOUNTS_CRAWL = _env_bool("ENABLE_OFFICIAL_ACCOUNTS_CRAWL", False)

# Xiaohongshu official accounts
_DEFAULT_XHS_OFFICIAL_ACCOUNTS = [
    {"user_id": "5bebb72379896c00014f3295", "name": "beijing_zhongguancun_college"},
    {"user_id": "68685a82000000001d009ebb", "name": "shanghai_chuangzhi_college"},
]
XHS_OFFICIAL_ACCOUNTS = _env_json_list("XHS_OFFICIAL_ACCOUNTS", _DEFAULT_XHS_OFFICIAL_ACCOUNTS)

# Bilibili official accounts
BILI_OFFICIAL_ACCOUNTS = [
    {"uid": 85843243, "name": "beijing_zhongguancun_college"},
]

LOGIN_TYPE = os.getenv("LOGIN_TYPE", "qrcode")  # qrcode | phone | cookie
COOKIES = os.getenv("COOKIES", "")
CRAWLER_TYPE = os.getenv("CRAWLER_TYPE", "search")  # search | detail | creator

# Whether to enable proxy
ENABLE_IP_PROXY = _env_bool("ENABLE_IP_PROXY", False)
IP_PROXY_POOL_COUNT = max(1, _env_int("IP_PROXY_POOL_COUNT", 2))
IP_PROXY_PROVIDER_NAME = os.getenv("IP_PROXY_PROVIDER_NAME", "kuaidaili")  # kuaidaili | wandouhttp

# Browser runtime behavior
HEADLESS = _env_bool("HEADLESS", False)
SAVE_LOGIN_STATE = _env_bool("SAVE_LOGIN_STATE", True)

# ==================== CDP (Chrome DevTools Protocol) ====================
CDP_DEBUG_PORT = _env_int("CDP_DEBUG_PORT", 9222)

# Remote CDP WebSocket URL (optional)
CDP_REMOTE_WS_URL = os.getenv("CDP_REMOTE_WS_URL", "")

# Automatically enable CDP mode when a remote URL is configured
ENABLE_CDP_MODE = bool(CDP_REMOTE_WS_URL)

# Optional headers for remote CDP handshake
CDP_REMOTE_HEADERS: dict[str, str] = {}

# Optional local browser binary path
CUSTOM_BROWSER_PATH = os.getenv("CUSTOM_BROWSER_PATH", "")
CDP_HEADLESS = _env_bool("CDP_HEADLESS", False)
BROWSER_LAUNCH_TIMEOUT = max(10, _env_int("BROWSER_LAUNCH_TIMEOUT", 60))
AUTO_CLOSE_BROWSER = _env_bool("AUTO_CLOSE_BROWSER", False)

# Storage settings
# Supported: json | csv | excel | sqlite | db | postgres | mongodb | supabase
SAVE_DATA_OPTION = os.getenv("SAVE_DATA_OPTION", "json")
SAVE_DATA_PATH = _DEFAULT_DATA_DIR

# Browser user data directory pattern
USER_DATA_DIR = "%s_user_data_dir"  # %s is platform name

# Crawl controls
START_PAGE = max(1, _env_int("START_PAGE", 1))
CRAWLER_MAX_NOTES_COUNT = max(1, _env_int("CRAWLER_MAX_NOTES_COUNT", 30))
MAX_CONCURRENCY_NUM = max(1, _env_int("MAX_CONCURRENCY_NUM", 1))
ENABLE_GET_MEIDAS = _env_bool("ENABLE_GET_MEIDAS", False)
ENABLE_GET_COMMENTS = _env_bool("ENABLE_GET_COMMENTS", True)
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max(
    1,
    _env_int("CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES", 20),
)
ENABLE_GET_SUB_COMMENTS = _env_bool("ENABLE_GET_SUB_COMMENTS", True)

# Word cloud
ENABLE_GET_WORDCLOUD = _env_bool("ENABLE_GET_WORDCLOUD", False)
CUSTOM_WORDS = {
    "零几": "年份",
    "gaopin_ci": "zhuanye_shuyu",
}
STOP_WORDS_FILE = str(_PROJECT_ROOT / "docs" / "hit_stopwords.txt")
FONT_PATH = str(_PROJECT_ROOT / "docs" / "STZHONGS.TTF")

# Request sleep interval (seconds)
CRAWLER_MAX_SLEEP_SEC = max(0, _env_int("CRAWLER_MAX_SLEEP_SEC", 5))

from .bilibili_config import *
from .xhs_config import *
from .dy_config import *
from .ks_config import *
from .weibo_config import *
from .tieba_config import *
from .zhihu_config import *
from .vibe_coding_config import *
