from __future__ import annotations

import os
import json
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import config
from tasks.common.crawl_planner import (
    normalize_chunk_size,
    normalize_parallel_limit,
    normalize_split_mode,
    plan_platform_value_jobs,
)

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    yaml = None

from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskFieldOption, TaskTemplate

DEFAULT_PLATFORMS = ["xhs", "dy", "bili", "zhihu"]
PLATFORM_LABELS = {
    "xhs": "Xiaohongshu",
    "dy": "Douyin",
    "bili": "Bilibili",
    "zhihu": "Zhihu",
    "wb": "Weibo",
    "tieba": "Baidu Tieba",
    "ks": "Kuaishou",
}
PLATFORM_OPTIONS = [
    TaskFieldOption(value=platform, label=label)
    for platform, label in PLATFORM_LABELS.items()
]
JOB_MODE_OPTIONS = [
    TaskFieldOption(value="auto", label="自动", description="默认优先按平台聚合，必要时再拆成多批 job。"),
    TaskFieldOption(value="bundle", label="按平台聚合", description="每个平台 1 个 job，内部顺序跑所有关键词或账号。"),
    TaskFieldOption(value="single", label="逐项拆分", description="平台 x 单关键词/账号 一项一个 job。"),
    TaskFieldOption(value="chunked", label="按批拆分", description="平台 x N 个关键词/账号 一批一个 job。"),
]
LOGIN_OPTIONS = [
    TaskFieldOption(value="qrcode", label="二维码登录"),
    TaskFieldOption(value="cookie", label="Cookie 登录"),
    TaskFieldOption(value="phone", label="手机号登录"),
]
BROWSER_PROVIDER_OPTIONS = [
    TaskFieldOption(value="local", label="本地浏览器"),
    TaskFieldOption(value="browsermint", label="Browsermint"),
]
SAVE_OPTIONS = [
    TaskFieldOption(value="json", label="JSON (Local Default)"),
    TaskFieldOption(value="csv", label="CSV"),
    TaskFieldOption(value="excel", label="Excel"),
    TaskFieldOption(value="sqlite", label="SQLite"),
    TaskFieldOption(value="db", label="MySQL"),
    TaskFieldOption(value="postgres", label="PostgreSQL"),
    TaskFieldOption(value="mongodb", label="MongoDB"),
    TaskFieldOption(value="supabase", label="Supabase"),
]
ALLOWED_LOGIN_TYPES = {option.value for option in LOGIN_OPTIONS}
ALLOWED_SAVE_OPTIONS = {option.value for option in SAVE_OPTIONS}
ALLOWED_BROWSER_PROVIDERS = {option.value for option in BROWSER_PROVIDER_OPTIONS}
_TASK_CONFIG_PATH = Path(__file__).with_name("config.yaml")
_TASK_CONFIG_WARNING_PREFIX = "[sentiment_monitor.task]"
DEFAULT_KEYWORD_JOB_MODE = "auto"
DEFAULT_KEYWORD_JOB_CHUNK_SIZE = 1
DEFAULT_KEYWORD_MAX_PARALLEL = 0
DEFAULT_CREATOR_JOB_MODE = "auto"
DEFAULT_CREATOR_JOB_CHUNK_SIZE = 1
DEFAULT_CREATOR_MAX_PARALLEL = 0

FALLBACK_KEYWORD_GROUPS = {
    "zgca_core": [
        "北京中关村学院",
        "中关村学院",
        "北京中关村学院招生",
        "北京中关村学院夏令营",
        "北京中关村学院博士生",
    ],
    "guozhi_linkage": [
        "中关村人工智能研究院",
        "刘铁岩",
        "邵斌",
        "深圳河套",
        "上海创智",
    ],
    "zgca_risk": [
        "北京中关村学院 避雷",
        "中关村学院 坑",
        "中关村学院 骗",
        "中关村学院 水",
        "中关村学院 垃圾",
        "中关村学院 投诉",
        "中关村学院 举报",
        "中关村学院 维权",
        "中关村学院 内定",
        "中关村学院 不公平",
        "中关村学院 黑幕",
        "中关村学院 退学",
        "中关村学院 劝退",
        "中关村学院 毕业",
        "中关村学院 师资差",
        "中关村学院 导师不负责",
        "中关村学院 招生黑幕",
        "中关村学院 夏令营 不公平",
    ],
    "zgca_scenario": [
        "北京中关村学院 怎么样",
        "中关村学院 值得去吗",
        "中关村学院 博士",
        "中关村学院 博士生",
        "中关村学院 直博",
        "中关村学院 夏令营",
        "中关村学院 招生",
        "中关村学院 宣讲",
        "中关村学院 面试",
        "中关村学院 考核",
        "中关村学院 毕业去向",
        "中关村学院 就业",
        "中关村学院 孵化",
        "中关村学院 创业",
        "中关村学院 融资",
        "中关村学院 对比",
        "中关村学院 vs",
        "中关村学院 不如",
        "中关村学院 野鸡",
        "中关村学院 骗子",
    ],
}
FALLBACK_GUOZHI_RISK_SUFFIXES = [
    "投诉",
    "举报",
    "维权",
    "不公平",
    "黑幕",
    "争议",
]


def _default_official_account_targets() -> list[str]:
    configured = getattr(config, "XHS_OFFICIAL_ACCOUNTS", []) or []
    targets: list[str] = []
    seen: set[str] = set()
    for item in configured:
        if not isinstance(item, Mapping):
            continue
        candidate = str(
            item.get("profile_url")
            or item.get("url")
            or item.get("user_id")
            or item.get("name")
            or ""
        ).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        targets.append(candidate)
    return targets


DEFAULT_OFFICIAL_ACCOUNT_TARGETS = _default_official_account_targets()

FALLBACK_TASK_CONFIG = {
    "default_inputs": {
        "platforms": ["xhs"],
        "keyword_groups": ["zgca_core", "guozhi_linkage", "zgca_risk", "zgca_scenario"],
        "keywords": [],
        "enable_keyword_search": True,
        "keyword_whitelist": [],
        "keyword_blacklist": [],
        "enable_relevance_filter": getattr(config, "ENABLE_RELEVANCE_FILTER", True),
        "relevance_must_contain": getattr(config, "RELEVANCE_MUST_CONTAIN", []),
        "relevance_exclude_keywords": getattr(config, "RELEVANCE_EXCLUDE_KEYWORDS", []),
        "max_notes_count": 30,
        "top_posts_count": 30,
        "enable_comments": False,
        "enable_sub_comments": False,
        "max_comments_count_singlenotes": getattr(
            config,
            "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES",
            20,
        ),
        "top_comments_count": getattr(
            config,
            "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES",
            20,
        ),
        "enable_account_crawl": False,
        "specified_account_ids": [],
        "account_whitelist": [],
        "account_blacklist": [],
        "enable_official_accounts_crawl": False,
        "official_account_targets": DEFAULT_OFFICIAL_ACCOUNT_TARGETS,
        "login_type": getattr(config, "LOGIN_TYPE", "qrcode"),
        "cookies": getattr(config, "COOKIES", ""),
        "save_option": "json",
        "headless": getattr(config, "HEADLESS", False),
    },
    "supported_platforms": ["xhs", "wb", "dy"],
    "keyword_groups": FALLBACK_KEYWORD_GROUPS,
    "keyword_defaults": {
        "whitelist": [],
        "blacklist": [],
    },
    "account_defaults": {
        "specified_account_ids": [],
        "whitelist": [],
        "blacklist": [],
    },
    "guozhi_risk_suffixes": FALLBACK_GUOZHI_RISK_SUFFIXES,
    "presets": [],
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _sanitize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = _split_csv(value)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _normalize_platforms(value: Any, fallback: list[str]) -> list[str]:
    platforms = _sanitize_string_list(value)
    if not platforms:
        platforms = list(fallback)
    valid_platforms = [platform for platform in platforms if platform in PLATFORM_LABELS]
    return valid_platforms or list(fallback)


def _normalize_login_type(value: Any, fallback: str) -> str:
    candidate = str(value).strip() if value is not None else fallback
    return candidate if candidate in ALLOWED_LOGIN_TYPES else fallback


def _normalize_save_option(value: Any, fallback: str) -> str:
    candidate = str(value).strip() if value is not None else fallback
    return candidate if candidate in ALLOWED_SAVE_OPTIONS else fallback


def _normalize_browser_provider(value: Any, fallback: str = "local") -> str:
    candidate = str(value).strip().lower() if value is not None else fallback
    return candidate if candidate in ALLOWED_BROWSER_PROVIDERS else fallback


def _normalize_cookie_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _normalize_keyword_text(value: Any, fallback: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value is not None and not _sanitize_string_list(value):
        return ""
    keywords = _sanitize_string_list(value)
    if not keywords:
        keywords = _sanitize_string_list(fallback)
    return ",".join(keywords)


def _csv_text(value: Any) -> str:
    return ",".join(_sanitize_string_list(value))


def _runtime_storage_backend_for(save_option: str) -> str:
    if save_option in {"json", "csv", "excel"}:
        return f"file:{save_option}"
    return save_option


def _warning(*, code: str, message: str, level: str = "warning", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "level": level,
        "message": message,
    }
    payload.update(extra)
    return payload


def _summarize_job_values(values: Sequence[str], limit: int = 24) -> str:
    preview = ",".join(str(value).strip() for value in values if str(value).strip())
    if len(preview) <= limit:
        return preview
    return f"{preview[: limit - 3]}..."


def _resolve_keywords_with_rules(
    keywords: Any,
    *,
    whitelist: Any = None,
    blacklist: Any = None,
) -> list[str]:
    combined = _sanitize_string_list(keywords) + _sanitize_string_list(whitelist)
    excluded = set(_sanitize_string_list(blacklist))
    return [keyword for keyword in _sanitize_string_list(combined) if keyword not in excluded]


def _resolve_account_ids(
    specified: Any,
    *,
    whitelist: Any = None,
    blacklist: Any = None,
) -> list[str]:
    combined = _sanitize_string_list(specified) + _sanitize_string_list(whitelist)
    excluded = set(_sanitize_string_list(blacklist))
    return [account_id for account_id in _sanitize_string_list(combined) if account_id not in excluded]


def _load_cookie(platform: str) -> str:
    try:
        import cookies_config  # type: ignore
    except ImportError:
        return ""

    get_cookie = getattr(cookies_config, "get_cookie", None)
    if callable(get_cookie):
        cookie = get_cookie(platform)
        if isinstance(cookie, str):
            return cookie.strip()
    return ""


def _keyword_csv(*groups: list[str]) -> str:
    keywords: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            keyword = item.strip()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword)
    return ",".join(keywords)


def _expand_keywords_with_suffixes(base_keywords: list[str], suffixes: list[str]) -> list[str]:
    expanded: list[str] = []
    for keyword in base_keywords:
        expanded.append(keyword)
        expanded.extend(f"{keyword} {suffix}" for suffix in suffixes)
    return expanded


def _normalize_external_task_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    if "defaults" in raw or "media_daily" in raw:
        defaults = raw.get("defaults", {})
        media_daily = raw.get("media_daily", {})
        candidate = {
            "default_inputs": defaults if isinstance(defaults, Mapping) else {},
            "supported_platforms": media_daily.get("supported_platforms", []),
            "keyword_groups": media_daily.get("keyword_groups", {}),
            "keyword_defaults": media_daily.get("keyword_defaults", {}),
            "account_defaults": media_daily.get("account_defaults", {}),
            "guozhi_risk_suffixes": media_daily.get("guozhi_risk_suffixes", []),
            "presets": media_daily.get("presets", raw.get("presets", [])),
        }
    else:
        candidate = dict(raw)

    default_inputs_raw = candidate.get("default_inputs", {})
    keyword_groups_raw = candidate.get("keyword_groups", {})
    keyword_defaults_raw = candidate.get("keyword_defaults", {})
    account_defaults_raw = candidate.get("account_defaults", {})
    presets_raw = candidate.get("presets", [])

    fallback_defaults = FALLBACK_TASK_CONFIG["default_inputs"]
    normalized_default_inputs = {
        "platforms": _normalize_platforms(
            default_inputs_raw.get("platforms"),
            list(fallback_defaults["platforms"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else list(fallback_defaults["platforms"]),
        "keyword_groups": _sanitize_string_list(
            default_inputs_raw.get("keyword_groups"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else list(fallback_defaults["keyword_groups"]),
        "keywords": _sanitize_string_list(default_inputs_raw.get("keywords"))
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "enable_keyword_search": _coerce_bool(
            default_inputs_raw.get("enable_keyword_search"),
            bool(fallback_defaults["enable_keyword_search"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_keyword_search"]),
        "keyword_whitelist": _sanitize_string_list(
            default_inputs_raw.get("keyword_whitelist"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "keyword_blacklist": _sanitize_string_list(
            default_inputs_raw.get("keyword_blacklist"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "enable_relevance_filter": _coerce_bool(
            default_inputs_raw.get("enable_relevance_filter"),
            bool(fallback_defaults["enable_relevance_filter"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_relevance_filter"]),
        "relevance_must_contain": _sanitize_string_list(
            default_inputs_raw.get("relevance_must_contain"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else list(fallback_defaults["relevance_must_contain"]),
        "relevance_exclude_keywords": _sanitize_string_list(
            default_inputs_raw.get("relevance_exclude_keywords"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else list(fallback_defaults["relevance_exclude_keywords"]),
        "max_notes_count": _coerce_int(
            default_inputs_raw.get(
                "max_notes_count",
                default_inputs_raw.get("top_posts_count"),
            ),
            int(fallback_defaults["max_notes_count"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else int(fallback_defaults["max_notes_count"]),
        "enable_comments": _coerce_bool(
            default_inputs_raw.get("enable_comments"),
            bool(fallback_defaults["enable_comments"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_comments"]),
        "enable_sub_comments": _coerce_bool(
            default_inputs_raw.get("enable_sub_comments"),
            bool(fallback_defaults["enable_sub_comments"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_sub_comments"]),
        "max_comments_count_singlenotes": _coerce_int(
            default_inputs_raw.get(
                "max_comments_count_singlenotes",
                default_inputs_raw.get("top_comments_count"),
            ),
            int(fallback_defaults["max_comments_count_singlenotes"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else int(fallback_defaults["max_comments_count_singlenotes"]),
        "enable_account_crawl": _coerce_bool(
            default_inputs_raw.get("enable_account_crawl"),
            bool(fallback_defaults["enable_account_crawl"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_account_crawl"]),
        "specified_account_ids": _sanitize_string_list(
            default_inputs_raw.get("specified_account_ids"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "account_whitelist": _sanitize_string_list(
            default_inputs_raw.get("account_whitelist"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "account_blacklist": _sanitize_string_list(
            default_inputs_raw.get("account_blacklist"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else [],
        "enable_official_accounts_crawl": _coerce_bool(
            default_inputs_raw.get("enable_official_accounts_crawl"),
            bool(fallback_defaults["enable_official_accounts_crawl"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["enable_official_accounts_crawl"]),
        "official_account_targets": _sanitize_string_list(
            default_inputs_raw.get("official_account_targets"),
        )
        if isinstance(default_inputs_raw, Mapping)
        else list(fallback_defaults["official_account_targets"]),
        "login_type": _normalize_login_type(
            default_inputs_raw.get("login_type"),
            str(fallback_defaults["login_type"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else str(fallback_defaults["login_type"]),
        "cookies": _normalize_cookie_text(
            default_inputs_raw.get("cookies"),
            str(fallback_defaults.get("cookies", "")),
        )
        if isinstance(default_inputs_raw, Mapping)
        else str(fallback_defaults.get("cookies", "")),
        "save_option": _normalize_save_option(
            default_inputs_raw.get("save_option"),
            str(fallback_defaults["save_option"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else str(fallback_defaults["save_option"]),
        "headless": _coerce_bool(
            default_inputs_raw.get("headless"),
            bool(fallback_defaults["headless"]),
        )
        if isinstance(default_inputs_raw, Mapping)
        else bool(fallback_defaults["headless"]),
    }

    normalized_keyword_groups: dict[str, list[str]] = {}
    if isinstance(keyword_groups_raw, Mapping):
        for name, values in keyword_groups_raw.items():
            group_name = str(name).strip()
            keywords = _sanitize_string_list(values)
            if group_name and keywords:
                normalized_keyword_groups[group_name] = keywords

    normalized_presets: list[dict[str, Any]] = []
    if isinstance(presets_raw, Sequence) and not isinstance(presets_raw, (bytes, bytearray, str)):
        for raw_preset in presets_raw:
            if not isinstance(raw_preset, Mapping):
                continue
            preset_id = str(raw_preset.get("id", "")).strip()
            name = str(raw_preset.get("name", "")).strip()
            if not preset_id or not name:
                continue
            normalized_presets.append(
                {
                    "id": preset_id,
                    "name": name,
                    "platforms": _normalize_platforms(
                        raw_preset.get("platforms"),
                        list(FALLBACK_TASK_CONFIG["supported_platforms"]),
                    ),
                    "keyword_groups": _sanitize_string_list(raw_preset.get("keyword_groups")),
                    "keywords": _sanitize_string_list(raw_preset.get("keywords")),
                    "enable_keyword_search": _coerce_bool(
                        raw_preset.get("enable_keyword_search"),
                        True,
                    ),
                    "keyword_whitelist": _sanitize_string_list(raw_preset.get("keyword_whitelist")),
                    "keyword_blacklist": _sanitize_string_list(raw_preset.get("keyword_blacklist")),
                    "enable_relevance_filter": _coerce_bool(
                        raw_preset.get("enable_relevance_filter"),
                        bool(fallback_defaults["enable_relevance_filter"]),
                    ),
                    "relevance_must_contain": raw_preset.get("relevance_must_contain"),
                    "relevance_exclude_keywords": raw_preset.get("relevance_exclude_keywords"),
                    "max_notes_count": _coerce_int(
                        raw_preset.get("max_notes_count", raw_preset.get("top_posts_count")),
                        30,
                    ),
                    "enable_comments": _coerce_bool(raw_preset.get("enable_comments"), False),
                    "enable_sub_comments": _coerce_bool(
                        raw_preset.get("enable_sub_comments"),
                        False,
                    ),
                    "max_comments_count_singlenotes": _coerce_int(
                        raw_preset.get(
                            "max_comments_count_singlenotes",
                            raw_preset.get("top_comments_count"),
                        ),
                        int(fallback_defaults["max_comments_count_singlenotes"]),
                    ),
                    "enable_account_crawl": _coerce_bool(
                        raw_preset.get("enable_account_crawl"),
                        False,
                    ),
                    "specified_account_ids": _sanitize_string_list(
                        raw_preset.get("specified_account_ids")
                    ),
                    "account_whitelist": _sanitize_string_list(raw_preset.get("account_whitelist")),
                    "account_blacklist": _sanitize_string_list(raw_preset.get("account_blacklist")),
                    "enable_official_accounts_crawl": _coerce_bool(
                        raw_preset.get("enable_official_accounts_crawl"),
                        False,
                    ),
                    "official_account_targets": _sanitize_string_list(
                        raw_preset.get("official_account_targets")
                    ),
                    "save_option": _normalize_save_option(
                        raw_preset.get("save_option"),
                        str(fallback_defaults["save_option"]),
                    ),
                    "is_default": _coerce_bool(raw_preset.get("is_default"), False),
                }
            )

    normalized = {
        "default_inputs": normalized_default_inputs,
        "supported_platforms": _normalize_platforms(
            candidate.get("supported_platforms"),
            list(FALLBACK_TASK_CONFIG["supported_platforms"]),
        ),
        "keyword_groups": normalized_keyword_groups,
        "keyword_defaults": {
            "whitelist": _sanitize_string_list(keyword_defaults_raw.get("whitelist"))
            if isinstance(keyword_defaults_raw, Mapping)
            else [],
            "blacklist": _sanitize_string_list(keyword_defaults_raw.get("blacklist"))
            if isinstance(keyword_defaults_raw, Mapping)
            else [],
        },
        "account_defaults": {
            "specified_account_ids": _sanitize_string_list(account_defaults_raw.get("specified_account_ids"))
            if isinstance(account_defaults_raw, Mapping)
            else [],
            "whitelist": _sanitize_string_list(account_defaults_raw.get("whitelist"))
            if isinstance(account_defaults_raw, Mapping)
            else [],
            "blacklist": _sanitize_string_list(account_defaults_raw.get("blacklist"))
            if isinstance(account_defaults_raw, Mapping)
            else [],
        },
        "guozhi_risk_suffixes": _sanitize_string_list(candidate.get("guozhi_risk_suffixes")),
        "presets": normalized_presets,
    }

    if not normalized["default_inputs"]["keyword_groups"] and not normalized["default_inputs"]["keywords"]:
        normalized["default_inputs"]["keyword_groups"] = list(
            FALLBACK_TASK_CONFIG["default_inputs"]["keyword_groups"]
        )

    return normalized


def _load_task_config() -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    if yaml is None and _TASK_CONFIG_PATH.exists():
        warnings.warn(
            f"{_TASK_CONFIG_WARNING_PREFIX} PyYAML is unavailable; "
            "falling back to hardcoded defaults.",
            stacklevel=2,
        )
    elif yaml is not None and _TASK_CONFIG_PATH.exists():
        try:
            raw = yaml.safe_load(_TASK_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(raw, Mapping):
                loaded = _normalize_external_task_config(raw)
        except Exception as exc:
            warnings.warn(
                f"{_TASK_CONFIG_WARNING_PREFIX} Failed to load {_TASK_CONFIG_PATH.name}: {exc}. "
                "Falling back to hardcoded defaults.",
                stacklevel=2,
            )
            loaded = {}

    fallback_defaults = FALLBACK_TASK_CONFIG["default_inputs"]
    loaded_defaults = loaded.get("default_inputs", {})
    loaded_keyword_groups = _sanitize_string_list(loaded_defaults.get("keyword_groups"))
    loaded_keywords = _sanitize_string_list(loaded_defaults.get("keywords"))
    if not loaded_keyword_groups and not loaded_keywords:
        loaded_keyword_groups = list(fallback_defaults["keyword_groups"])
    keyword_groups = {
        name: list(values)
        for name, values in FALLBACK_TASK_CONFIG["keyword_groups"].items()
    }
    keyword_groups.update(loaded.get("keyword_groups", {}))
    keyword_defaults = {
        "whitelist": _sanitize_string_list(loaded.get("keyword_defaults", {}).get("whitelist")),
        "blacklist": _sanitize_string_list(loaded.get("keyword_defaults", {}).get("blacklist")),
    }
    account_defaults = {
        "specified_account_ids": _sanitize_string_list(
            loaded.get("account_defaults", {}).get("specified_account_ids")
        ),
        "whitelist": _sanitize_string_list(loaded.get("account_defaults", {}).get("whitelist")),
        "blacklist": _sanitize_string_list(loaded.get("account_defaults", {}).get("blacklist")),
    }

    default_inputs = {
        "platforms": _normalize_platforms(
            loaded_defaults.get("platforms"),
            list(fallback_defaults["platforms"]),
        ),
        "keyword_groups": loaded_keyword_groups,
        "keywords": loaded_keywords,
        "enable_keyword_search": _coerce_bool(
            loaded_defaults.get("enable_keyword_search"),
            bool(fallback_defaults["enable_keyword_search"]),
        ),
        "keyword_whitelist": _sanitize_string_list(loaded_defaults.get("keyword_whitelist"))
        or list(keyword_defaults["whitelist"]),
        "keyword_blacklist": _sanitize_string_list(loaded_defaults.get("keyword_blacklist"))
        or list(keyword_defaults["blacklist"]),
        "enable_relevance_filter": _coerce_bool(
            loaded_defaults.get("enable_relevance_filter"),
            bool(fallback_defaults["enable_relevance_filter"]),
        ),
        "relevance_must_contain": _sanitize_string_list(loaded_defaults.get("relevance_must_contain"))
        or list(fallback_defaults["relevance_must_contain"]),
        "relevance_exclude_keywords": _sanitize_string_list(
            loaded_defaults.get("relevance_exclude_keywords")
        )
        or list(fallback_defaults["relevance_exclude_keywords"]),
        "max_notes_count": max(
            1,
            _coerce_int(
                loaded_defaults.get("max_notes_count", loaded_defaults.get("top_posts_count")),
                int(fallback_defaults["max_notes_count"]),
            ),
        ),
        "enable_comments": _coerce_bool(
            loaded_defaults.get("enable_comments"),
            bool(fallback_defaults["enable_comments"]),
        ),
        "enable_sub_comments": _coerce_bool(
            loaded_defaults.get("enable_sub_comments"),
            bool(fallback_defaults["enable_sub_comments"]),
        ),
        "max_comments_count_singlenotes": max(
            1,
            _coerce_int(
                loaded_defaults.get(
                    "max_comments_count_singlenotes",
                    loaded_defaults.get("top_comments_count"),
                ),
                int(fallback_defaults["max_comments_count_singlenotes"]),
            ),
        ),
        "enable_account_crawl": _coerce_bool(
            loaded_defaults.get("enable_account_crawl"),
            bool(fallback_defaults["enable_account_crawl"]),
        ),
        "specified_account_ids": _sanitize_string_list(loaded_defaults.get("specified_account_ids"))
        or list(account_defaults["specified_account_ids"]),
        "account_whitelist": _sanitize_string_list(loaded_defaults.get("account_whitelist"))
        or list(account_defaults["whitelist"]),
        "account_blacklist": _sanitize_string_list(loaded_defaults.get("account_blacklist"))
        or list(account_defaults["blacklist"]),
        "enable_official_accounts_crawl": _coerce_bool(
            loaded_defaults.get("enable_official_accounts_crawl"),
            bool(fallback_defaults["enable_official_accounts_crawl"]),
        ),
        "official_account_targets": _sanitize_string_list(
            loaded_defaults.get("official_account_targets")
        )
        or list(fallback_defaults["official_account_targets"]),
        "login_type": _normalize_login_type(
            loaded_defaults.get("login_type"),
            str(fallback_defaults["login_type"]),
        ),
        "cookies": _normalize_cookie_text(
            loaded_defaults.get("cookies"),
            str(fallback_defaults.get("cookies", "")),
        ),
        "save_option": _normalize_save_option(
            loaded_defaults.get("save_option"),
            str(fallback_defaults["save_option"]),
        ),
        "headless": _coerce_bool(
            loaded_defaults.get("headless"),
            bool(fallback_defaults["headless"]),
        ),
    }
    if not default_inputs["enable_comments"]:
        default_inputs["enable_sub_comments"] = False

    supported_platforms = _normalize_platforms(
        loaded.get("supported_platforms"),
        list(FALLBACK_TASK_CONFIG["supported_platforms"]),
    )
    guozhi_risk_suffixes = _sanitize_string_list(loaded.get("guozhi_risk_suffixes"))
    if not guozhi_risk_suffixes:
        guozhi_risk_suffixes = list(FALLBACK_TASK_CONFIG["guozhi_risk_suffixes"])

    return {
        "default_inputs": default_inputs,
        "supported_platforms": supported_platforms,
        "keyword_groups": keyword_groups,
        "keyword_defaults": keyword_defaults,
        "account_defaults": account_defaults,
        "guozhi_risk_suffixes": guozhi_risk_suffixes,
        "presets": list(loaded.get("presets", [])),
    }


def _resolve_keywords(*, keyword_groups: list[str] | None = None, keywords: Any = None) -> list[str]:
    resolved_groups = keyword_groups or []
    grouped_keywords = [
        keyword
        for group_name in resolved_groups
        for keyword in TASK_CONFIG["keyword_groups"].get(group_name, [])
    ]
    explicit_keywords = _sanitize_string_list(keywords)
    return _sanitize_string_list(grouped_keywords + explicit_keywords)


TASK_CONFIG = _load_task_config()
KEYWORD_GROUPS: dict[str, list[str]] = dict(TASK_CONFIG["keyword_groups"])
DEFAULT_INPUTS = dict(TASK_CONFIG["default_inputs"])
SUPPORTED_MEDIA_DAILY_PLATFORMS = list(TASK_CONFIG["supported_platforms"])
GOUZHI_RISK_SUFFIXES = list(TASK_CONFIG["guozhi_risk_suffixes"])
DEFAULT_KEYWORDS = _resolve_keywords(
    keyword_groups=list(DEFAULT_INPUTS["keyword_groups"]),
    keywords=DEFAULT_INPUTS["keywords"],
)
UI_DEFAULT_PARAMS = {
    "platforms": list(DEFAULT_INPUTS["platforms"]),
    "keywords": _keyword_csv(DEFAULT_KEYWORDS),
    "enable_keyword_search": bool(DEFAULT_INPUTS["enable_keyword_search"]),
    "keyword_whitelist": _csv_text(DEFAULT_INPUTS["keyword_whitelist"]),
    "keyword_blacklist": _csv_text(DEFAULT_INPUTS["keyword_blacklist"]),
    "keyword_job_mode": DEFAULT_KEYWORD_JOB_MODE,
    "keyword_job_chunk_size": DEFAULT_KEYWORD_JOB_CHUNK_SIZE,
    "keyword_job_max_parallel": DEFAULT_KEYWORD_MAX_PARALLEL,
    "enable_relevance_filter": bool(DEFAULT_INPUTS["enable_relevance_filter"]),
    "relevance_must_contain": _csv_text(DEFAULT_INPUTS["relevance_must_contain"]),
    "relevance_exclude_keywords": _csv_text(DEFAULT_INPUTS["relevance_exclude_keywords"]),
    "max_notes_count": int(DEFAULT_INPUTS["max_notes_count"]),
    "top_posts_count": int(DEFAULT_INPUTS["max_notes_count"]),
    "enable_comments": bool(DEFAULT_INPUTS["enable_comments"]),
    "enable_sub_comments": bool(DEFAULT_INPUTS["enable_sub_comments"]),
    "max_comments_count_singlenotes": int(DEFAULT_INPUTS["max_comments_count_singlenotes"]),
    "top_comments_count": int(DEFAULT_INPUTS["max_comments_count_singlenotes"]),
    "enable_account_crawl": bool(DEFAULT_INPUTS["enable_account_crawl"]),
    "specified_account_ids": _csv_text(DEFAULT_INPUTS["specified_account_ids"]),
    "account_whitelist": _csv_text(DEFAULT_INPUTS["account_whitelist"]),
    "account_blacklist": _csv_text(DEFAULT_INPUTS["account_blacklist"]),
    "enable_official_accounts_crawl": bool(DEFAULT_INPUTS["enable_official_accounts_crawl"]),
    "official_account_targets": _csv_text(DEFAULT_INPUTS["official_account_targets"]),
    "creator_job_mode": DEFAULT_CREATOR_JOB_MODE,
    "creator_job_chunk_size": DEFAULT_CREATOR_JOB_CHUNK_SIZE,
    "creator_job_max_parallel": DEFAULT_CREATOR_MAX_PARALLEL,
    "login_type": str(DEFAULT_INPUTS["login_type"]),
    "cookies": _normalize_cookie_text(DEFAULT_INPUTS.get("cookies", "")),
    "browser_provider": "local",
    "browser_session_id": "",
    "save_option": str(DEFAULT_INPUTS["save_option"]),
    "headless": bool(DEFAULT_INPUTS["headless"]),
}


def _build_seed_params(
    *,
    platforms: list[str],
    max_notes_count: int,
    enable_comments: bool,
    keyword_groups: list[str] | None = None,
    keywords: Any = None,
    enable_relevance_filter: bool | None = None,
    relevance_must_contain: Any = None,
    relevance_exclude_keywords: Any = None,
    enable_sub_comments: bool = False,
    max_comments_count_singlenotes: int | None = None,
    save_option: str | None = None,
    is_default: bool = False,
) -> dict[str, Any]:
    resolved_keywords = _resolve_keywords(keyword_groups=keyword_groups, keywords=keywords)
    if not resolved_keywords:
        resolved_keywords = list(DEFAULT_KEYWORDS)
    params = {
        "platforms": _normalize_platforms(platforms, list(UI_DEFAULT_PARAMS["platforms"])),
        "keywords": _keyword_csv(resolved_keywords),
        "enable_keyword_search": True,
        "keyword_whitelist": "",
        "keyword_blacklist": "",
        "keyword_job_mode": UI_DEFAULT_PARAMS["keyword_job_mode"],
        "keyword_job_chunk_size": UI_DEFAULT_PARAMS["keyword_job_chunk_size"],
        "keyword_job_max_parallel": UI_DEFAULT_PARAMS["keyword_job_max_parallel"],
        "enable_relevance_filter": (
            UI_DEFAULT_PARAMS["enable_relevance_filter"]
            if enable_relevance_filter is None
            else bool(enable_relevance_filter)
        ),
        "relevance_must_contain": (
            UI_DEFAULT_PARAMS["relevance_must_contain"]
            if relevance_must_contain is None
            else _csv_text(relevance_must_contain)
        ),
        "relevance_exclude_keywords": (
            UI_DEFAULT_PARAMS["relevance_exclude_keywords"]
            if relevance_exclude_keywords is None
            else _csv_text(relevance_exclude_keywords)
        ),
        "max_notes_count": max(1, int(max_notes_count)),
        "top_posts_count": max(1, int(max_notes_count)),
        "enable_comments": bool(enable_comments),
        "enable_sub_comments": bool(enable_sub_comments and enable_comments),
        "max_comments_count_singlenotes": max(
            1,
            int(
                max_comments_count_singlenotes
                if max_comments_count_singlenotes is not None
                else UI_DEFAULT_PARAMS["max_comments_count_singlenotes"]
            ),
        ),
        "top_comments_count": max(
            1,
            int(
                max_comments_count_singlenotes
                if max_comments_count_singlenotes is not None
                else UI_DEFAULT_PARAMS["max_comments_count_singlenotes"]
            ),
        ),
        "enable_account_crawl": False,
        "specified_account_ids": "",
        "account_whitelist": "",
        "account_blacklist": "",
        "enable_official_accounts_crawl": False,
        "official_account_targets": "",
        "creator_job_mode": UI_DEFAULT_PARAMS["creator_job_mode"],
        "creator_job_chunk_size": UI_DEFAULT_PARAMS["creator_job_chunk_size"],
        "creator_job_max_parallel": UI_DEFAULT_PARAMS["creator_job_max_parallel"],
        "login_type": UI_DEFAULT_PARAMS["login_type"],
        "cookies": "",
        "browser_provider": UI_DEFAULT_PARAMS["browser_provider"],
        "browser_session_id": UI_DEFAULT_PARAMS["browser_session_id"],
        "save_option": _normalize_save_option(
            save_option,
            UI_DEFAULT_PARAMS["save_option"],
        ),
        "headless": UI_DEFAULT_PARAMS["headless"],
    }
    if is_default:
        params["platforms"] = list(UI_DEFAULT_PARAMS["platforms"])
    return params


def _build_media_daily_preset_seeds() -> list[PresetSeed]:
    default_keyword_groups = list(DEFAULT_INPUTS["keyword_groups"])
    seeds = [
        PresetSeed(
            id="preset_sentiment_xhs_posts_only",
            task_slug="sentiment_monitor",
            name="小红书舆情-纯帖子版",
            params=_build_seed_params(
                platforms=["xhs"],
                keyword_groups=default_keyword_groups,
                max_notes_count=30,
                enable_comments=False,
                save_option="json",
            ),
            is_default=False,
        ),
        PresetSeed(
            id="preset_sentiment_media_daily_report",
            task_slug="sentiment_monitor",
            name="媒体监测日报-全量词包",
            params=_build_seed_params(
                platforms=list(UI_DEFAULT_PARAMS["platforms"]),
                keyword_groups=default_keyword_groups,
                max_notes_count=int(UI_DEFAULT_PARAMS["max_notes_count"]),
                enable_comments=bool(UI_DEFAULT_PARAMS["enable_comments"]),
                enable_sub_comments=bool(UI_DEFAULT_PARAMS["enable_sub_comments"]),
                max_comments_count_singlenotes=int(UI_DEFAULT_PARAMS["max_comments_count_singlenotes"]),
                save_option=str(UI_DEFAULT_PARAMS["save_option"]),
                is_default=True,
            ),
            is_default=True,
        ),
        PresetSeed(
            id="preset_sentiment_media_daily_zgca_positive",
            task_slug="sentiment_monitor",
            name="媒体监测日报-ZGCA正中性",
            params=_build_seed_params(
                platforms=list(SUPPORTED_MEDIA_DAILY_PLATFORMS),
                keyword_groups=["zgca_core", "zgca_scenario"],
                max_notes_count=30,
                enable_comments=False,
                save_option="json",
            ),
            is_default=False,
        ),
        PresetSeed(
            id="preset_sentiment_media_daily_zgca_risk",
            task_slug="sentiment_monitor",
            name="媒体监测日报-ZGCA风险",
            params=_build_seed_params(
                platforms=list(SUPPORTED_MEDIA_DAILY_PLATFORMS),
                keyword_groups=["zgca_risk"],
                max_notes_count=30,
                enable_comments=True,
                save_option="json",
            ),
            is_default=False,
        ),
        PresetSeed(
            id="preset_sentiment_media_daily_guozhi_positive",
            task_slug="sentiment_monitor",
            name="媒体监测日报-国智院联动正中性",
            params=_build_seed_params(
                platforms=list(SUPPORTED_MEDIA_DAILY_PLATFORMS),
                keyword_groups=["guozhi_linkage"],
                max_notes_count=30,
                enable_comments=False,
                save_option="json",
            ),
            is_default=False,
        ),
        PresetSeed(
            id="preset_sentiment_media_daily_guozhi_risk",
            task_slug="sentiment_monitor",
            name="媒体监测日报-国智院联动风险",
            params=_build_seed_params(
                platforms=list(SUPPORTED_MEDIA_DAILY_PLATFORMS),
                keywords=_expand_keywords_with_suffixes(
                    TASK_CONFIG["keyword_groups"].get("guozhi_linkage", []),
                    list(GOUZHI_RISK_SUFFIXES),
                ),
                max_notes_count=30,
                enable_comments=True,
                save_option="json",
            ),
            is_default=False,
        ),
    ]

    for preset in TASK_CONFIG["presets"]:
        preset_keywords = _resolve_keywords(
            keyword_groups=list(preset.get("keyword_groups", [])),
            keywords=preset.get("keywords"),
        )
        if not preset_keywords:
            continue
        seeds.append(
            PresetSeed(
                id=f"preset_sentiment_{preset['id']}",
                task_slug="sentiment_monitor",
                name=str(preset["name"]),
                params=_build_seed_params(
                    platforms=list(preset["platforms"]),
                    keywords=preset_keywords,
                    max_notes_count=int(preset["max_notes_count"]),
                    enable_comments=bool(preset["enable_comments"]),
                    enable_sub_comments=bool(preset["enable_sub_comments"]),
                    max_comments_count_singlenotes=int(
                        preset["max_comments_count_singlenotes"]
                    ),
                    enable_relevance_filter=preset.get("enable_relevance_filter"),
                    relevance_must_contain=preset.get("relevance_must_contain"),
                    relevance_exclude_keywords=preset.get("relevance_exclude_keywords"),
                    save_option=str(preset["save_option"]),
                ),
                is_default=bool(preset["is_default"]),
            )
        )

    return seeds


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="sentiment_monitor",
        title="舆情监控",
        description="按平台和关键词运行内容抓取任务，支持媒体监测日报默认词包和业务预设。",
        defaults=dict(UI_DEFAULT_PARAMS),
        capabilities=[
            "多平台关键词搜索",
            "评论与二级评论可配",
            "运行前可预览解析出的实际命令",
            "业务词包默认值由 config.yaml 注入",
        ],
        fields=[
            TaskField(
                key="platforms",
                component="multiselect",
                label="平台",
                default=list(UI_DEFAULT_PARAMS["platforms"]),
                group="采集范围",
                required=True,
                options=PLATFORM_OPTIONS,
                validation={"min_items": 1},
            ),
            TaskField(
                key="enable_keyword_search",
                component="switch",
                label="启用关键词搜索",
                default=UI_DEFAULT_PARAMS["enable_keyword_search"],
                group="采集范围",
            ),
            TaskField(
                key="keywords",
                component="textarea",
                label="关键词",
                default=UI_DEFAULT_PARAMS["keywords"],
                description="多个关键词用英文逗号分隔。",
                group="采集范围",
                required=True,
                validation={"min_length": 1},
                visible_when={"enable_keyword_search": True},
            ),
            TaskField(
                key="keyword_whitelist",
                component="textarea",
                label="关键词白名单",
                default=UI_DEFAULT_PARAMS["keyword_whitelist"],
                description="会追加到关键词集合中。",
                group="采集范围",
                visible_when={"enable_keyword_search": True},
            ),
            TaskField(
                key="keyword_blacklist",
                component="textarea",
                label="关键词黑名单",
                default=UI_DEFAULT_PARAMS["keyword_blacklist"],
                description="会从最终关键词集合中移除。",
                group="采集范围",
                visible_when={"enable_keyword_search": True},
            ),
            TaskField(
                key="keyword_job_mode",
                component="select",
                label="关键词任务拆分",
                default=UI_DEFAULT_PARAMS["keyword_job_mode"],
                description="决定关键词是按平台聚合、逐项拆分还是按批拆分成多个 job。",
                group="执行编排",
                options=JOB_MODE_OPTIONS,
                visible_when={"enable_keyword_search": True},
            ),
            TaskField(
                key="keyword_job_chunk_size",
                component="number",
                label="关键词每批数量",
                default=UI_DEFAULT_PARAMS["keyword_job_chunk_size"],
                description="仅在按批拆分时生效。",
                group="执行编排",
                validation={"min": 1, "max": 100},
                visible_when={"enable_keyword_search": True, "keyword_job_mode": "chunked"},
            ),
            TaskField(
                key="keyword_job_max_parallel",
                component="number",
                label="关键词并发上限",
                default=UI_DEFAULT_PARAMS["keyword_job_max_parallel"],
                description="填 0 表示自动：默认单平台最多 2 个并发，多平台默认每个平台 1 个 job。",
                group="执行编排",
                validation={"min": 0, "max": 64},
                visible_when={"enable_keyword_search": True},
            ),
            TaskField(
                key="max_notes_count",
                component="number",
                label="每个平台 Top 帖子数",
                default=UI_DEFAULT_PARAMS["max_notes_count"],
                group="内容控制",
                validation={"min": 1, "max": 200},
            ),
            TaskField(
                key="enable_relevance_filter",
                component="switch",
                label="启用相关性过滤",
                default=UI_DEFAULT_PARAMS["enable_relevance_filter"],
                group="内容控制",
                helper_text="开启后，爬虫会基于包含词/排除词筛掉不相关内容。",
            ),
            TaskField(
                key="relevance_must_contain",
                component="textarea",
                label="相关性包含词",
                default=UI_DEFAULT_PARAMS["relevance_must_contain"],
                group="内容控制",
                description="多个词用英文逗号分隔，命中任一词即视为相关。",
                visible_when={"enable_relevance_filter": True},
            ),
            TaskField(
                key="relevance_exclude_keywords",
                component="textarea",
                label="相关性排除词",
                default=UI_DEFAULT_PARAMS["relevance_exclude_keywords"],
                group="内容控制",
                description="多个词用英文逗号分隔，命中任一词即剔除。",
                visible_when={"enable_relevance_filter": True},
            ),
            TaskField(
                key="enable_comments",
                component="switch",
                label="抓取评论",
                default=UI_DEFAULT_PARAMS["enable_comments"],
                group="内容控制",
            ),
            TaskField(
                key="enable_sub_comments",
                component="switch",
                label="抓取二级评论",
                default=UI_DEFAULT_PARAMS["enable_sub_comments"],
                group="内容控制",
                visible_when={"enable_comments": True},
            ),
            TaskField(
                key="max_comments_count_singlenotes",
                component="number",
                label="每条内容 Top 评论数",
                default=UI_DEFAULT_PARAMS["max_comments_count_singlenotes"],
                group="内容控制",
                visible_when={"enable_comments": True},
                validation={"min": 1, "max": 200},
            ),
            TaskField(
                key="enable_account_crawl",
                component="switch",
                label="启用指定账号抓取",
                default=UI_DEFAULT_PARAMS["enable_account_crawl"],
                group="账号定向",
            ),
            TaskField(
                key="specified_account_ids",
                component="textarea",
                label="指定账号 ID",
                default=UI_DEFAULT_PARAMS["specified_account_ids"],
                description="多个账号 ID 用英文逗号分隔。",
                group="账号定向",
                visible_when={"enable_account_crawl": True},
            ),
            TaskField(
                key="account_whitelist",
                component="textarea",
                label="账号白名单",
                default=UI_DEFAULT_PARAMS["account_whitelist"],
                group="账号定向",
                visible_when={"enable_account_crawl": True},
            ),
            TaskField(
                key="account_blacklist",
                component="textarea",
                label="账号黑名单",
                default=UI_DEFAULT_PARAMS["account_blacklist"],
                group="账号定向",
                visible_when={"enable_account_crawl": True},
            ),
            TaskField(
                key="enable_official_accounts_crawl",
                component="switch",
                label="启用官方号抓取",
                default=UI_DEFAULT_PARAMS["enable_official_accounts_crawl"],
                group="账号定向",
                helper_text="仅在任务显式开启时执行，避免全局配置偷偷插入官方号阶段。",
            ),
            TaskField(
                key="official_account_targets",
                component="textarea",
                label="官方号目标",
                default=UI_DEFAULT_PARAMS["official_account_targets"],
                description="多个 profile_url / user_id 用英文逗号分隔。XHS 建议优先填 profile_url。",
                group="账号定向",
                visible_when={"enable_official_accounts_crawl": True},
            ),
            TaskField(
                key="creator_job_mode",
                component="select",
                label="账号任务拆分",
                default=UI_DEFAULT_PARAMS["creator_job_mode"],
                description="决定账号抓取是按平台聚合、逐账号拆分还是按批拆分。",
                group="执行编排",
                options=JOB_MODE_OPTIONS,
                visible_when={"enable_account_crawl": True},
            ),
            TaskField(
                key="creator_job_chunk_size",
                component="number",
                label="账号每批数量",
                default=UI_DEFAULT_PARAMS["creator_job_chunk_size"],
                description="仅在按批拆分时生效。",
                group="执行编排",
                validation={"min": 1, "max": 100},
                visible_when={"enable_account_crawl": True, "creator_job_mode": "chunked"},
            ),
            TaskField(
                key="creator_job_max_parallel",
                component="number",
                label="账号并发上限",
                default=UI_DEFAULT_PARAMS["creator_job_max_parallel"],
                description="填 0 表示自动，系统会优先保持每个平台 1 个活跃 job。",
                group="执行编排",
                validation={"min": 0, "max": 64},
                visible_when={"enable_account_crawl": True},
            ),
            TaskField(
                key="browser_provider",
                component="select",
                label="浏览器提供方",
                default=UI_DEFAULT_PARAMS["browser_provider"],
                group="运行配置",
                options=BROWSER_PROVIDER_OPTIONS,
            ),
            TaskField(
                key="browser_session_id",
                component="select",
                label="Browsermint 会话",
                default=UI_DEFAULT_PARAMS["browser_session_id"],
                group="运行配置",
                options=[],
                helper_text="选择一个已登录的 Browsermint 会话。启动任务时会即时换取新的 CDP 连接信息。",
                visible_when={"browser_provider": "browsermint"},
            ),
            TaskField(
                key="login_type",
                component="select",
                label="登录方式",
                default=UI_DEFAULT_PARAMS["login_type"],
                group="运行配置",
                options=LOGIN_OPTIONS,
                visible_when={"browser_provider": "local"},
            ),
            TaskField(
                key="save_option",
                component="select",
                label="保存方式",
                default=UI_DEFAULT_PARAMS["save_option"],
                group="运行配置",
                options=SAVE_OPTIONS,
            ),
            TaskField(
                key="cookies",
                component="textarea",
                label="Cookie 内容",
                default=UI_DEFAULT_PARAMS["cookies"],
                group="运行配置",
                rows=4,
                layout="full",
                placeholder="粘贴完整 Cookie 字符串，例如 a=1; b=2",
                helper_text="仅在 Cookie 登录时生效。若留空，则回退读取 cookies_config.py 中的平台 Cookie。",
                visible_when={"login_type": "cookie", "browser_provider": "local"},
            ),
            TaskField(
                key="headless",
                component="switch",
                label="无头模式",
                default=UI_DEFAULT_PARAMS["headless"],
                group="运行配置",
                helper_text="二维码登录会自动关闭无头模式，确保浏览器窗口可见并可扫码。",
                visible_when={"browser_provider": "local"},
                disabled_when={"login_type": "qrcode"},
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    max_notes_count = _coerce_int(
        raw.get("max_notes_count", raw.get("top_posts_count")),
        UI_DEFAULT_PARAMS["max_notes_count"],
    )
    max_comments_count = _coerce_int(
        raw.get("max_comments_count_singlenotes", raw.get("top_comments_count")),
        UI_DEFAULT_PARAMS["max_comments_count_singlenotes"],
    )
    keywords = _normalize_keyword_text(
        raw.get("keywords"),
        UI_DEFAULT_PARAMS["keywords"],
        allow_empty="keywords" in raw,
    )
    keyword_whitelist = _normalize_keyword_text(
        raw.get("keyword_whitelist"),
        UI_DEFAULT_PARAMS["keyword_whitelist"],
        allow_empty="keyword_whitelist" in raw,
    )
    keyword_blacklist = _normalize_keyword_text(
        raw.get("keyword_blacklist"),
        UI_DEFAULT_PARAMS["keyword_blacklist"],
        allow_empty="keyword_blacklist" in raw,
    )
    relevance_must_contain = _normalize_keyword_text(
        raw.get("relevance_must_contain"),
        UI_DEFAULT_PARAMS["relevance_must_contain"],
        allow_empty="relevance_must_contain" in raw,
    )
    relevance_exclude_keywords = _normalize_keyword_text(
        raw.get("relevance_exclude_keywords"),
        UI_DEFAULT_PARAMS["relevance_exclude_keywords"],
        allow_empty="relevance_exclude_keywords" in raw,
    )
    resolved_keywords = _resolve_keywords_with_rules(
        keywords,
        whitelist=keyword_whitelist,
        blacklist=keyword_blacklist,
    )
    specified_account_ids = _normalize_keyword_text(
        raw.get("specified_account_ids", raw.get("creator_ids")),
        UI_DEFAULT_PARAMS["specified_account_ids"],
        allow_empty="specified_account_ids" in raw or "creator_ids" in raw,
    )
    account_whitelist = _normalize_keyword_text(
        raw.get("account_whitelist"),
        UI_DEFAULT_PARAMS["account_whitelist"],
        allow_empty="account_whitelist" in raw,
    )
    account_blacklist = _normalize_keyword_text(
        raw.get("account_blacklist"),
        UI_DEFAULT_PARAMS["account_blacklist"],
        allow_empty="account_blacklist" in raw,
    )
    resolved_account_ids = _resolve_account_ids(
        specified_account_ids,
        whitelist=account_whitelist,
        blacklist=account_blacklist,
    )
    official_account_targets = _normalize_keyword_text(
        raw.get("official_account_targets"),
        UI_DEFAULT_PARAMS["official_account_targets"],
        allow_empty="official_account_targets" in raw,
    )
    enable_keyword_search = _coerce_bool(
        raw.get("enable_keyword_search"),
        UI_DEFAULT_PARAMS["enable_keyword_search"],
    )
    enable_account_crawl = _coerce_bool(
        raw.get("enable_account_crawl"),
        UI_DEFAULT_PARAMS["enable_account_crawl"] or bool(resolved_account_ids),
    )
    enable_official_accounts_crawl = _coerce_bool(
        raw.get("enable_official_accounts_crawl"),
        UI_DEFAULT_PARAMS["enable_official_accounts_crawl"],
    )
    keyword_job_mode = normalize_split_mode(
        raw.get("keyword_job_mode"),
        UI_DEFAULT_PARAMS["keyword_job_mode"],
    )
    creator_job_mode = normalize_split_mode(
        raw.get("creator_job_mode"),
        UI_DEFAULT_PARAMS["creator_job_mode"],
    )
    params = {
        "platforms": _normalize_platforms(raw.get("platforms"), list(UI_DEFAULT_PARAMS["platforms"])),
        "keywords": _csv_text(resolved_keywords),
        "enable_keyword_search": enable_keyword_search,
        "keyword_whitelist": _csv_text(keyword_whitelist),
        "keyword_blacklist": _csv_text(keyword_blacklist),
        "keyword_job_mode": keyword_job_mode,
        "keyword_job_chunk_size": normalize_chunk_size(
            raw.get("keyword_job_chunk_size"),
            UI_DEFAULT_PARAMS["keyword_job_chunk_size"],
        ),
        "keyword_job_max_parallel": normalize_parallel_limit(
            raw.get("keyword_job_max_parallel"),
            UI_DEFAULT_PARAMS["keyword_job_max_parallel"],
        ),
        "enable_relevance_filter": _coerce_bool(
            raw.get("enable_relevance_filter"),
            UI_DEFAULT_PARAMS["enable_relevance_filter"],
        ),
        "relevance_must_contain": _csv_text(relevance_must_contain),
        "relevance_exclude_keywords": _csv_text(relevance_exclude_keywords),
        "max_notes_count": max_notes_count,
        "top_posts_count": max_notes_count,
        "enable_comments": _coerce_bool(raw.get("enable_comments"), UI_DEFAULT_PARAMS["enable_comments"]),
        "enable_sub_comments": _coerce_bool(
            raw.get("enable_sub_comments"),
            UI_DEFAULT_PARAMS["enable_sub_comments"],
        ),
        "max_comments_count_singlenotes": max_comments_count,
        "top_comments_count": max_comments_count,
        "enable_account_crawl": enable_account_crawl,
        "specified_account_ids": _csv_text(resolved_account_ids),
        "creator_ids": _csv_text(resolved_account_ids),
        "account_whitelist": _csv_text(account_whitelist),
        "account_blacklist": _csv_text(account_blacklist),
        "enable_official_accounts_crawl": enable_official_accounts_crawl,
        "official_account_targets": _csv_text(official_account_targets),
        "creator_job_mode": creator_job_mode,
        "creator_job_chunk_size": normalize_chunk_size(
            raw.get("creator_job_chunk_size"),
            UI_DEFAULT_PARAMS["creator_job_chunk_size"],
        ),
        "creator_job_max_parallel": normalize_parallel_limit(
            raw.get("creator_job_max_parallel"),
            UI_DEFAULT_PARAMS["creator_job_max_parallel"],
        ),
        "browser_provider": _normalize_browser_provider(raw.get("browser_provider"), UI_DEFAULT_PARAMS["browser_provider"]),
        "browser_session_id": str(raw.get("browser_session_id") or "").strip(),
        "login_type": _normalize_login_type(raw.get("login_type"), UI_DEFAULT_PARAMS["login_type"]),
        "cookies": _normalize_cookie_text(raw.get("cookies"), UI_DEFAULT_PARAMS["cookies"]),
        "save_option": _normalize_save_option(raw.get("save_option"), UI_DEFAULT_PARAMS["save_option"]),
        "headless": _coerce_bool(raw.get("headless"), UI_DEFAULT_PARAMS["headless"]),
    }
    if params["browser_provider"] == "browsermint":
        params["login_type"] = "qrcode"
        params["cookies"] = ""
        params["headless"] = False
    if params["login_type"] == "qrcode":
        # QR login requires a visible browser window for manual scan/verification.
        params["headless"] = False
    if params["max_notes_count"] < 1:
        raise ValueError("max_notes_count must be greater than 0.")
    if params["max_comments_count_singlenotes"] < 1:
        raise ValueError("max_comments_count_singlenotes must be greater than 0.")
    if not params["enable_comments"]:
        params["enable_sub_comments"] = False
    if params["enable_keyword_search"] and not params["keywords"]:
        raise ValueError("Keywords cannot be empty when keyword search is enabled.")
    if params["enable_account_crawl"] and not params["specified_account_ids"]:
        raise ValueError("specified_account_ids cannot be empty when account crawl is enabled.")
    if params["enable_official_accounts_crawl"] and not params["official_account_targets"]:
        raise ValueError(
            "official_account_targets cannot be empty when official account crawl is enabled."
        )
    if (
        not params["enable_keyword_search"]
        and not params["enable_account_crawl"]
        and not params["enable_official_accounts_crawl"]
    ):
        raise ValueError("At least one crawl stage must be enabled.")
    return params


def _resolve_runtime_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    if params is not None:
        return normalize_params(params)
    return normalize_params(
        {
            "platforms": os.getenv("SENTIMENT_PLATFORMS", list(UI_DEFAULT_PARAMS["platforms"])),
            "keywords": os.getenv("SENTIMENT_KEYWORDS", UI_DEFAULT_PARAMS["keywords"]),
            "enable_keyword_search": os.getenv(
                "SENTIMENT_ENABLE_KEYWORD_SEARCH",
                "true" if UI_DEFAULT_PARAMS["enable_keyword_search"] else "false",
            ),
            "keyword_whitelist": os.getenv(
                "SENTIMENT_KEYWORD_WHITELIST",
                UI_DEFAULT_PARAMS["keyword_whitelist"],
            ),
            "keyword_blacklist": os.getenv(
                "SENTIMENT_KEYWORD_BLACKLIST",
                UI_DEFAULT_PARAMS["keyword_blacklist"],
            ),
            "keyword_job_mode": os.getenv(
                "SENTIMENT_KEYWORD_JOB_MODE",
                UI_DEFAULT_PARAMS["keyword_job_mode"],
            ),
            "keyword_job_chunk_size": os.getenv(
                "SENTIMENT_KEYWORD_JOB_CHUNK_SIZE",
                str(UI_DEFAULT_PARAMS["keyword_job_chunk_size"]),
            ),
            "keyword_job_max_parallel": os.getenv(
                "SENTIMENT_KEYWORD_JOB_MAX_PARALLEL",
                str(UI_DEFAULT_PARAMS["keyword_job_max_parallel"]),
            ),
            "enable_relevance_filter": os.getenv(
                "SENTIMENT_ENABLE_RELEVANCE_FILTER",
                "true" if UI_DEFAULT_PARAMS["enable_relevance_filter"] else "false",
            ),
            "relevance_must_contain": os.getenv(
                "SENTIMENT_RELEVANCE_MUST_CONTAIN",
                UI_DEFAULT_PARAMS["relevance_must_contain"],
            ),
            "relevance_exclude_keywords": os.getenv(
                "SENTIMENT_RELEVANCE_EXCLUDE_KEYWORDS",
                UI_DEFAULT_PARAMS["relevance_exclude_keywords"],
            ),
            "max_notes_count": os.getenv(
                "SENTIMENT_MAX_NOTES_COUNT",
                str(UI_DEFAULT_PARAMS["max_notes_count"]),
            ),
            "enable_comments": os.getenv(
                "SENTIMENT_GET_COMMENT",
                "true" if UI_DEFAULT_PARAMS["enable_comments"] else "false",
            ),
            "enable_sub_comments": os.getenv(
                "SENTIMENT_GET_SUB_COMMENT",
                "true" if UI_DEFAULT_PARAMS["enable_sub_comments"] else "false",
            ),
            "max_comments_count_singlenotes": os.getenv(
                "SENTIMENT_MAX_COMMENTS_COUNT_SINGLENOTES",
                str(UI_DEFAULT_PARAMS["max_comments_count_singlenotes"]),
            ),
            "enable_account_crawl": os.getenv(
                "SENTIMENT_ENABLE_ACCOUNT_CRAWL",
                "true" if UI_DEFAULT_PARAMS["enable_account_crawl"] else "false",
            ),
            "specified_account_ids": os.getenv(
                "SENTIMENT_SPECIFIED_ACCOUNT_IDS",
                UI_DEFAULT_PARAMS["specified_account_ids"],
            ),
            "account_whitelist": os.getenv(
                "SENTIMENT_ACCOUNT_WHITELIST",
                UI_DEFAULT_PARAMS["account_whitelist"],
            ),
            "account_blacklist": os.getenv(
                "SENTIMENT_ACCOUNT_BLACKLIST",
                UI_DEFAULT_PARAMS["account_blacklist"],
            ),
            "enable_official_accounts_crawl": os.getenv(
                "SENTIMENT_ENABLE_OFFICIAL_ACCOUNTS_CRAWL",
                "true" if UI_DEFAULT_PARAMS["enable_official_accounts_crawl"] else "false",
            ),
            "official_account_targets": os.getenv(
                "SENTIMENT_OFFICIAL_ACCOUNT_TARGETS",
                UI_DEFAULT_PARAMS["official_account_targets"],
            ),
            "creator_job_mode": os.getenv(
                "SENTIMENT_CREATOR_JOB_MODE",
                UI_DEFAULT_PARAMS["creator_job_mode"],
            ),
            "creator_job_chunk_size": os.getenv(
                "SENTIMENT_CREATOR_JOB_CHUNK_SIZE",
                str(UI_DEFAULT_PARAMS["creator_job_chunk_size"]),
            ),
            "creator_job_max_parallel": os.getenv(
                "SENTIMENT_CREATOR_JOB_MAX_PARALLEL",
                str(UI_DEFAULT_PARAMS["creator_job_max_parallel"]),
            ),
            "browser_provider": os.getenv("BROWSER_PROVIDER", UI_DEFAULT_PARAMS["browser_provider"]),
            "browser_session_id": os.getenv("BROWSERMINT_SESSION_ID", UI_DEFAULT_PARAMS["browser_session_id"]),
            "login_type": os.getenv("SENTIMENT_LOGIN_TYPE", UI_DEFAULT_PARAMS["login_type"]),
            "cookies": os.getenv("SENTIMENT_COOKIES", UI_DEFAULT_PARAMS["cookies"]),
            "save_option": os.getenv("SENTIMENT_SAVE_OPTION", UI_DEFAULT_PARAMS["save_option"]),
            "headless": os.getenv(
                "SENTIMENT_HEADLESS",
                "true" if UI_DEFAULT_PARAMS["headless"] else "false",
            ),
        }
    )


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    normalized = _resolve_runtime_params(params)
    login_type = str(normalized["login_type"])
    cookie_input = _normalize_cookie_text(normalized.get("cookies"), "")
    browser_provider = str(normalized["browser_provider"])
    browsermint_single_session_safe = browser_provider == "browsermint"
    runtime_storage_backend = _runtime_storage_backend_for(str(normalized["save_option"]))
    platform_cookie_map: dict[str, str] = {}
    if login_type == "cookie":
        if cookie_input:
            for platform in normalized["platforms"]:
                platform_cookie_map[platform] = cookie_input
        else:
            missing_cookie_platforms: list[str] = []
            for platform in normalized["platforms"]:
                platform_cookie = _load_cookie(platform)
                if platform_cookie:
                    platform_cookie_map[platform] = platform_cookie
                else:
                    missing_cookie_platforms.append(platform)
            if missing_cookie_platforms:
                labels = ", ".join(PLATFORM_LABELS.get(item, item) for item in missing_cookie_platforms)
                raise ValueError(
                    f"已选择 Cookie 登录，但未提供 Cookie，且 cookies_config.py 中也没有这些平台的 Cookie: {labels}。"
                )

    stages: list[TaskStage] = []
    plan_warnings: list[dict[str, Any]] = []
    effective_plan_stages: list[dict[str, Any]] = []

    if browsermint_single_session_safe and not normalized["browser_session_id"]:
        plan_warnings.append(
            _warning(
                code="waiting_user",
                message="尚未选择 BrowserMint 会话，任务启动时会停在预检阶段并等待用户处理。",
                level="warning",
            )
        )

    def build_common_job_env(*, enable_official_accounts: bool) -> dict[str, str]:
        return {
            "ENABLE_RELEVANCE_FILTER": "true" if normalized["enable_relevance_filter"] else "false",
            "RELEVANCE_MUST_CONTAIN": normalized["relevance_must_contain"],
            "RELEVANCE_EXCLUDE_KEYWORDS": normalized["relevance_exclude_keywords"],
            "ENABLE_OFFICIAL_ACCOUNTS_CRAWL": "true" if enable_official_accounts else "false",
            "SOCIAL_CRAWLER_EFFECTIVE_SAVE_OPTION": str(normalized["save_option"]),
            "SOCIAL_CRAWLER_RUNTIME_STORAGE_BACKEND": runtime_storage_backend,
        }

    def maybe_record_parallelism_warning(
        *,
        stage_key: str,
        stage_name: str,
        requested_job_mode: str,
        effective_job_mode: str,
        requested_stage_max_parallel: int,
        effective_stage_max_parallel: int,
        requested_job_count: int,
        effective_job_count: int,
    ) -> None:
        if not browsermint_single_session_safe:
            return
        if (
            requested_job_mode == effective_job_mode
            and requested_stage_max_parallel == effective_stage_max_parallel
            and requested_job_count == effective_job_count
        ):
            return
        plan_warnings.append(
            _warning(
                code="degraded_parallelism",
                level="warning",
                message=(
                    f"{stage_name} 已切换为 BrowserMint 单会话安全模式："
                    f"job_mode {requested_job_mode} -> {effective_job_mode}，"
                    f"并发 {requested_stage_max_parallel} -> {effective_stage_max_parallel}。"
                ),
                stage_key=stage_key,
                issue_group="browsermint_session_contention",
                resource_mode="browsermint_single_session_safe",
            )
        )

    for crawl_type, stage_key, stage_name, stage_value_key, flag in (
        (
            "search",
            "sentiment_keyword_parallel_crawl",
            "Sentiment keyword search crawl",
            "keywords",
            "--keywords",
        ),
        (
            "creator",
            "sentiment_creator_parallel_crawl",
            "Sentiment creator target crawl",
            "specified_account_ids",
            "--creator_id",
        ),
    ):
        enabled = normalized["enable_keyword_search"] if crawl_type == "search" else normalized["enable_account_crawl"]
        stage_value = normalized[stage_value_key]
        if not enabled or not stage_value:
            continue

        requested_values = _sanitize_string_list(stage_value)
        requested_job_mode = (
            normalized["keyword_job_mode"]
            if crawl_type == "search"
            else normalized["creator_job_mode"]
        )
        requested_chunk_size = (
            normalized["keyword_job_chunk_size"]
            if crawl_type == "search"
            else normalized["creator_job_chunk_size"]
        )
        requested_parallel = (
            normalized["keyword_job_max_parallel"]
            if crawl_type == "search"
            else normalized["creator_job_max_parallel"]
        )
        requested_job_slices, requested_stage_max_parallel = plan_platform_value_jobs(
            normalized["platforms"],
            requested_values,
            split_mode=requested_job_mode,
            chunk_size=requested_chunk_size,
            max_parallel=requested_parallel,
        )
        effective_job_mode = "bundle" if browsermint_single_session_safe else requested_job_mode
        effective_chunk_size = (
            max(1, len(requested_values))
            if browsermint_single_session_safe
            else requested_chunk_size
        )
        job_slices, stage_max_parallel = plan_platform_value_jobs(
            normalized["platforms"],
            requested_values,
            split_mode=effective_job_mode,
            chunk_size=effective_chunk_size,
            max_parallel=1 if browsermint_single_session_safe else requested_parallel,
        )
        requested_stage_max_parallel = int(requested_stage_max_parallel or 0)
        stage_max_parallel = int(stage_max_parallel or 0)
        if browsermint_single_session_safe and job_slices:
            stage_max_parallel = 1
        maybe_record_parallelism_warning(
            stage_key=stage_key,
            stage_name=stage_name,
            requested_job_mode=requested_job_mode,
            effective_job_mode=effective_job_mode,
            requested_stage_max_parallel=requested_stage_max_parallel,
            effective_stage_max_parallel=stage_max_parallel,
            requested_job_count=len(requested_job_slices),
            effective_job_count=len(job_slices),
        )

        jobs: list[TaskJob] = []
        slice_kind = "keywords" if crawl_type == "search" else "accounts"
        for job_slice in job_slices:
            platform = job_slice.platform
            cookie = platform_cookie_map.get(platform, "")
            slice_value = job_slice.csv_value
            job_label = _summarize_job_values(job_slice.values)
            suffix = (
                f" [{job_slice.group_index}/{job_slice.group_total}] {job_label}"
                if job_slice.group_total > 1
                else (f" {job_label}" if len(job_slice.values) == 1 else "")
            )
            command = [
                python_executable,
                "main.py",
                "--platform",
                platform,
                "--lt",
                login_type,
                "--type",
                crawl_type,
                flag,
                slice_value,
                "--save_data_option",
                normalized["save_option"],
                "--max_notes_count",
                str(normalized["max_notes_count"]),
                "--get_comment",
                "true" if normalized["enable_comments"] else "false",
                "--get_sub_comment",
                "true" if normalized["enable_sub_comments"] else "false",
                "--max_comments_count_singlenotes",
                str(normalized["max_comments_count_singlenotes"]),
                "--headless",
                "true" if normalized["headless"] else "false",
            ]
            if cookie:
                command.extend(["--cookies", cookie])
            jobs.append(
                TaskJob(
                    key=(
                        f"{crawl_type}_{platform}_{job_slice.group_index:02d}"
                        if job_slice.group_total > 1
                        else f"{crawl_type}_{platform}"
                    ),
                    name=f"{PLATFORM_LABELS.get(platform, platform)} {crawl_type} crawl{suffix}",
                    command=command,
                    cwd=project_root,
                    env=build_common_job_env(enable_official_accounts=False),
                    metadata={
                        "crawl_type": crawl_type,
                        "platform": platform,
                        "platform_label": PLATFORM_LABELS.get(platform, platform),
                        "values": list(job_slice.values),
                        "slice_kind": slice_kind,
                        "slice_label": f"{PLATFORM_LABELS.get(platform, platform)} {slice_kind}",
                        "group_index": job_slice.group_index,
                        "group_total": job_slice.group_total,
                        "value_count": len(job_slice.values),
                        "job_mode": effective_job_mode,
                        "requested_job_mode": requested_job_mode,
                        "browser_provider": browser_provider,
                        "browser_session_id": normalized["browser_session_id"],
                        "resource_mode": (
                            "browsermint_single_session_safe"
                            if browsermint_single_session_safe
                            else "default"
                        ),
                    },
                )
            )
        stages.append(
            TaskStage(
                key=stage_key,
                name=stage_name,
                jobs=jobs,
                concurrent=not browsermint_single_session_safe,
                max_parallel=stage_max_parallel or None,
                abort_on_failure=False,
            )
        )
        effective_plan_stages.append(
            {
                "key": stage_key,
                "name": stage_name,
                "crawl_type": crawl_type,
                "requested_job_mode": requested_job_mode,
                "effective_job_mode": effective_job_mode,
                "requested_job_count": len(requested_job_slices),
                "effective_job_count": len(job_slices),
                "requested_max_parallel": requested_stage_max_parallel,
                "effective_max_parallel": stage_max_parallel,
                "resource_mode": (
                    "browsermint_single_session_safe"
                    if browsermint_single_session_safe
                    else "default"
                ),
                "value_count": len(requested_values),
                "values_preview": requested_values[:8],
            }
        )

    official_targets = _sanitize_string_list(normalized["official_account_targets"])
    if normalized["enable_official_accounts_crawl"]:
        official_platforms = [platform for platform in normalized["platforms"] if platform == "xhs"]
        ignored_platforms = [platform for platform in normalized["platforms"] if platform not in official_platforms]
        if ignored_platforms:
            ignored_labels = ", ".join(PLATFORM_LABELS.get(platform, platform) for platform in ignored_platforms)
            plan_warnings.append(
                _warning(
                    code="official_accounts_platform_ignored",
                    level="info",
                    message=f"官方号抓取当前仅接入 XHS，已忽略这些平台: {ignored_labels}。",
                )
            )
        if official_platforms and official_targets:
            official_jobs: list[TaskJob] = []
            serialized_targets = json.dumps(
                [
                    (
                        {"profile_url": target}
                        if target.startswith("http://") or target.startswith("https://")
                        else {"user_id": target}
                    )
                    for target in official_targets
                ],
                ensure_ascii=False,
            )
            for platform in official_platforms:
                cookie = platform_cookie_map.get(platform, "")
                command = [
                    python_executable,
                    "main.py",
                    "--platform",
                    platform,
                    "--lt",
                    login_type,
                    "--type",
                    "official_accounts",
                    "--save_data_option",
                    normalized["save_option"],
                    "--max_notes_count",
                    str(normalized["max_notes_count"]),
                    "--get_comment",
                    "true" if normalized["enable_comments"] else "false",
                    "--get_sub_comment",
                    "true" if normalized["enable_sub_comments"] else "false",
                    "--max_comments_count_singlenotes",
                    str(normalized["max_comments_count_singlenotes"]),
                    "--headless",
                    "true" if normalized["headless"] else "false",
                ]
                if cookie:
                    command.extend(["--cookies", cookie])
                env = build_common_job_env(enable_official_accounts=True)
                env.update(
                    {
                        "XHS_OFFICIAL_ACCOUNTS_JSON": serialized_targets,
                        "SOCIAL_CRAWLER_XHS_OFFICIAL_ACCOUNT_TARGETS": ",".join(official_targets),
                    }
                )
                official_jobs.append(
                    TaskJob(
                        key=f"official_accounts_{platform}",
                        name=f"{PLATFORM_LABELS.get(platform, platform)} official account crawl",
                        command=command,
                        cwd=project_root,
                        env=env,
                        metadata={
                            "crawl_type": "official_accounts",
                            "platform": platform,
                            "platform_label": PLATFORM_LABELS.get(platform, platform),
                            "values": list(official_targets),
                            "slice_kind": "official_accounts",
                            "slice_label": f"{PLATFORM_LABELS.get(platform, platform)} official accounts",
                            "group_index": 1,
                            "group_total": 1,
                            "value_count": len(official_targets),
                            "job_mode": "bundle",
                            "requested_job_mode": "bundle",
                            "browser_provider": browser_provider,
                            "browser_session_id": normalized["browser_session_id"],
                            "resource_mode": (
                                "browsermint_single_session_safe"
                                if browsermint_single_session_safe
                                else "default"
                            ),
                        },
                    )
                )
            stages.append(
                TaskStage(
                    key="sentiment_official_account_crawl",
                    name="Sentiment official account crawl",
                    jobs=official_jobs,
                    concurrent=False,
                    max_parallel=1,
                    abort_on_failure=False,
                )
            )
            effective_plan_stages.append(
                {
                    "key": "sentiment_official_account_crawl",
                    "name": "Sentiment official account crawl",
                    "crawl_type": "official_accounts",
                    "requested_job_mode": "bundle",
                    "effective_job_mode": "bundle",
                    "requested_job_count": len(official_jobs),
                    "effective_job_count": len(official_jobs),
                    "requested_max_parallel": 1,
                    "effective_max_parallel": 1,
                    "resource_mode": (
                        "browsermint_single_session_safe"
                        if browsermint_single_session_safe
                        else "default"
                    ),
                    "value_count": len(official_targets),
                    "values_preview": official_targets[:8],
                }
            )

    effective_plan: dict[str, Any] = {
        "mode": (
            "browsermint_single_session_safe"
            if browsermint_single_session_safe
            else "default"
        ),
        "browser_provider": browser_provider,
        "browser_session_id": normalized["browser_session_id"],
        "requested_save_option": normalized["save_option"],
        "effective_save_option": normalized["save_option"],
        "runtime_storage_backend": runtime_storage_backend,
        "stage_count": len(effective_plan_stages),
        "stages": effective_plan_stages,
    }
    if browsermint_single_session_safe:
        effective_plan["preflight_steps"] = [
            {"key": "connect_session", "label": "连接 BrowserMint 会话", "status": "pending"},
            {"key": "validate_login", "label": "校验登录态", "status": "pending"},
            {"key": "verify_homepage", "label": "验证首页可访问", "status": "pending"},
            {"key": "verify_runtime_readiness", "label": "验证轻量读取能力", "status": "pending"},
            {"key": "generate_plan", "label": "生成有效执行计划", "status": "pending"},
        ]

    return TaskSpec(
        slug="sentiment_monitor",
        title="Sentiment Monitor",
        short_desc="Parallel sentiment crawl across social platforms",
        capabilities=[
            "Task-template driven sentiment monitoring",
            "Media-daily keyword defaults from config.yaml",
            "Editable platform / keyword / creator runtime parameters",
        ],
        welcome_lines=[
            "Mission: run configurable sentiment monitoring.",
            f"Keyword search: {'enabled' if normalized['enable_keyword_search'] else 'disabled'}",
            f"Keywords: {normalized['keywords'] or 'n/a'}",
            f"Relevance filter: {'enabled' if normalized['enable_relevance_filter'] else 'disabled'}",
            f"Relevance must contain: {normalized['relevance_must_contain'] or 'n/a'}",
            f"Relevance exclude: {normalized['relevance_exclude_keywords'] or 'n/a'}",
            f"Creator crawl: {'enabled' if normalized['enable_account_crawl'] else 'disabled'}",
            f"Creator IDs: {normalized['specified_account_ids'] or 'n/a'}",
            f"Official accounts: {'enabled' if normalized['enable_official_accounts_crawl'] else 'disabled'}",
            f"Official targets: {normalized['official_account_targets'] or 'n/a'}",
            f"Platforms: {', '.join(PLATFORM_LABELS.get(p, p) for p in normalized['platforms'])}",
            f"Comments: {'enabled' if normalized['enable_comments'] else 'disabled'}",
            f"Browser: {normalized['browser_provider']} / {normalized['browser_session_id'] or 'local-session'}",
            f"Save option: {normalized['save_option']}",
            f"Runtime storage backend: {runtime_storage_backend}",
            f"Login: {normalized['login_type']} / headless={normalized['headless']} / cookie={'set' if cookie_input else 'unset'}",
        ],
        stages=stages,
        aliases=["sentiment", "monitor"],
        metadata={
            "effective_plan": effective_plan,
            "plan_warnings": plan_warnings,
            "warnings": list(plan_warnings),
            "effective_save_option": normalized["save_option"],
            "runtime_storage_backend": runtime_storage_backend,
        },
    )


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=_build_media_daily_preset_seeds(),
    )
