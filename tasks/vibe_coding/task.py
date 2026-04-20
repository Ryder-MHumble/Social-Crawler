from __future__ import annotations

import os
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

import vibe_coding.config as vc_cfg
from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskFieldOption, TaskTemplate

PLATFORM_LABELS = {
    "xhs": "Xiaohongshu",
    "bili": "Bilibili",
    "dy": "Douyin",
    "wb": "Weibo",
}
PLATFORM_OPTIONS = [
    TaskFieldOption(value=platform, label=label)
    for platform, label in PLATFORM_LABELS.items()
]
FALLBACK_CONFIG = {
    "default_inputs": {
        "platforms": list(getattr(vc_cfg, "VIBE_CODING_PLATFORMS", ["xhs", "bili"])),
        "enable_keyword_search": True,
        "keywords": list(getattr(vc_cfg, "SEARCH_KEYWORDS", [])),
        "keyword_whitelist": [],
        "keyword_blacklist": [],
        "scenario_words": ["vibe coding", "ai编程实战", "用ai做独立产品"],
        "max_notes_count": getattr(vc_cfg, "VIBE_CODING_MAX_NOTES_PER_KEYWORD", 20),
        "enable_comments": False,
        "enable_sub_comments": False,
        "max_comments_count_singlenotes": getattr(vc_cfg, "VIBE_CODING_TOP_COMMENTS_COUNT", 20),
        "enable_account_crawl": False,
        "specified_account_ids": [],
        "account_whitelist": [],
        "account_blacklist": [],
        "min_engagement": getattr(vc_cfg, "VIBE_CODING_MIN_ENGAGEMENT", 5),
        "keyword_score_threshold": getattr(vc_cfg, "KEYWORD_SCORE_THRESHOLD", 4),
    },
    "presets": [
        {"id": "default", "name": "Vibe Radar 默认版", "is_default": True},
        {
            "id": "creator_targets",
            "name": "Vibe Radar 指定账号版",
            "enable_keyword_search": False,
            "enable_account_crawl": True,
            "specified_account_ids": ["208259", "3546598241724373"],
        },
    ],
}
_TASK_CONFIG_PATH = Path(__file__).with_name("config.yaml")
_TASK_CONFIG_WARNING_PREFIX = "[vibe_coding.task]"


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


def _sanitize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
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


def _csv(value: Any) -> str:
    return ",".join(_sanitize_list(value))


def _normalize_platforms(value: Any, fallback: list[str]) -> list[str]:
    platforms = _sanitize_list(value) or list(fallback)
    valid = [platform for platform in platforms if platform in PLATFORM_LABELS]
    return valid or list(fallback)


def _resolve_keywords(keywords: Any, whitelist: Any, blacklist: Any, scenarios: Any) -> list[str]:
    combined = _sanitize_list(keywords) + _sanitize_list(whitelist) + _sanitize_list(scenarios)
    excluded = set(_sanitize_list(blacklist))
    return [item for item in _sanitize_list(combined) if item not in excluded]


def _resolve_accounts(specified: Any, whitelist: Any, blacklist: Any) -> list[str]:
    combined = _sanitize_list(specified) + _sanitize_list(whitelist)
    excluded = set(_sanitize_list(blacklist))
    return [item for item in _sanitize_list(combined) if item not in excluded]


def _load_config() -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    if yaml is None and _TASK_CONFIG_PATH.exists():
        warnings.warn(
            f"{_TASK_CONFIG_WARNING_PREFIX} PyYAML is unavailable; falling back to defaults.",
            stacklevel=2,
        )
    elif yaml is not None and _TASK_CONFIG_PATH.exists():
        try:
            raw = yaml.safe_load(_TASK_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(raw, Mapping):
                loaded = dict(raw)
        except Exception as exc:
            warnings.warn(
                f"{_TASK_CONFIG_WARNING_PREFIX} Failed to load {_TASK_CONFIG_PATH.name}: {exc}.",
                stacklevel=2,
            )
    defaults = dict(FALLBACK_CONFIG["default_inputs"])
    defaults.update(dict(loaded.get("default_inputs", {})))
    for key in (
        "platforms",
        "keywords",
        "keyword_whitelist",
        "keyword_blacklist",
        "scenario_words",
        "specified_account_ids",
        "account_whitelist",
        "account_blacklist",
    ):
        defaults[key] = _sanitize_list(defaults.get(key))
    return {
        "default_inputs": defaults,
        "presets": [
            dict(item)
            for item in loaded.get("presets", FALLBACK_CONFIG["presets"])
            if isinstance(item, Mapping)
        ],
    }


TASK_CONFIG = _load_config()
DEFAULT_INPUTS = dict(TASK_CONFIG["default_inputs"])
DEFAULT_PARAMS = {
    "platforms": list(DEFAULT_INPUTS["platforms"]),
    "enable_keyword_search": bool(DEFAULT_INPUTS["enable_keyword_search"]),
    "keywords": _csv(DEFAULT_INPUTS["keywords"]),
    "search_keywords": _csv(DEFAULT_INPUTS["keywords"]),
    "keyword_whitelist": _csv(DEFAULT_INPUTS["keyword_whitelist"]),
    "keyword_blacklist": _csv(DEFAULT_INPUTS["keyword_blacklist"]),
    "scenario_words": _csv(DEFAULT_INPUTS["scenario_words"]),
    "max_notes_count": int(DEFAULT_INPUTS["max_notes_count"]),
    "max_notes_per_keyword": int(DEFAULT_INPUTS["max_notes_count"]),
    "enable_comments": bool(DEFAULT_INPUTS["enable_comments"]),
    "enable_sub_comments": bool(DEFAULT_INPUTS["enable_sub_comments"]),
    "max_comments_count_singlenotes": int(DEFAULT_INPUTS["max_comments_count_singlenotes"]),
    "top_comments_count": int(DEFAULT_INPUTS["max_comments_count_singlenotes"]),
    "enable_account_crawl": bool(DEFAULT_INPUTS["enable_account_crawl"]),
    "specified_account_ids": _csv(DEFAULT_INPUTS["specified_account_ids"]),
    "creator_ids": _csv(DEFAULT_INPUTS["specified_account_ids"]),
    "account_whitelist": _csv(DEFAULT_INPUTS["account_whitelist"]),
    "account_blacklist": _csv(DEFAULT_INPUTS["account_blacklist"]),
    "min_engagement": int(DEFAULT_INPUTS["min_engagement"]),
    "keyword_score_threshold": int(DEFAULT_INPUTS["keyword_score_threshold"]),
}


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="vibe_coding",
        title="Vibe Coding 雷达",
        description="面向 AI 编程热点的配置化监测任务，支持关键词和指定账号两种抓取阶段。",
        defaults=dict(DEFAULT_PARAMS),
        capabilities=[
            "配置驱动的 vibe-coding 关键词词包和场景词",
            "关键词搜索与指定账号抓取双阶段编排",
            "兼容旧版 search_keywords/max_notes_per_keyword 参数",
        ],
        fields=[
            TaskField(key="platforms", component="multiselect", label="平台", default=list(DEFAULT_PARAMS["platforms"]), group="采集范围", required=True, options=PLATFORM_OPTIONS, validation={"min_items": 1}),
            TaskField(key="enable_keyword_search", component="switch", label="启用关键词搜索", default=DEFAULT_PARAMS["enable_keyword_search"], group="采集范围"),
            TaskField(key="keywords", component="textarea", label="关键词", default=DEFAULT_PARAMS["keywords"], group="采集范围", visible_when={"enable_keyword_search": True}),
            TaskField(key="keyword_whitelist", component="textarea", label="关键词白名单", default=DEFAULT_PARAMS["keyword_whitelist"], group="采集范围", visible_when={"enable_keyword_search": True}),
            TaskField(key="keyword_blacklist", component="textarea", label="关键词黑名单", default=DEFAULT_PARAMS["keyword_blacklist"], group="采集范围", visible_when={"enable_keyword_search": True}),
            TaskField(key="scenario_words", component="textarea", label="场景词", default=DEFAULT_PARAMS["scenario_words"], group="采集范围", visible_when={"enable_keyword_search": True}),
            TaskField(key="max_notes_count", component="number", label="每个平台 Top 帖子数", default=DEFAULT_PARAMS["max_notes_count"], group="内容控制", validation={"min": 1, "max": 100}),
            TaskField(key="min_engagement", component="number", label="最低互动量", default=DEFAULT_PARAMS["min_engagement"], group="内容控制", validation={"min": 0}),
            TaskField(key="keyword_score_threshold", component="number", label="关键词分数阈值", default=DEFAULT_PARAMS["keyword_score_threshold"], group="内容控制", validation={"min": 0}),
            TaskField(key="enable_comments", component="switch", label="抓取评论", default=DEFAULT_PARAMS["enable_comments"], group="内容控制"),
            TaskField(key="enable_sub_comments", component="switch", label="抓取二级评论", default=DEFAULT_PARAMS["enable_sub_comments"], group="内容控制", visible_when={"enable_comments": True}),
            TaskField(key="max_comments_count_singlenotes", component="number", label="每条内容 Top 评论数", default=DEFAULT_PARAMS["max_comments_count_singlenotes"], group="内容控制", visible_when={"enable_comments": True}, validation={"min": 1, "max": 200}),
            TaskField(key="enable_account_crawl", component="switch", label="启用指定账号抓取", default=DEFAULT_PARAMS["enable_account_crawl"], group="账号定向"),
            TaskField(key="specified_account_ids", component="textarea", label="指定账号 ID", default=DEFAULT_PARAMS["specified_account_ids"], group="账号定向", visible_when={"enable_account_crawl": True}),
            TaskField(key="account_whitelist", component="textarea", label="账号白名单", default=DEFAULT_PARAMS["account_whitelist"], group="账号定向", visible_when={"enable_account_crawl": True}),
            TaskField(key="account_blacklist", component="textarea", label="账号黑名单", default=DEFAULT_PARAMS["account_blacklist"], group="账号定向", visible_when={"enable_account_crawl": True}),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    max_notes_count = _coerce_int(
        raw.get("max_notes_count", raw.get("max_notes_per_keyword")),
        DEFAULT_PARAMS["max_notes_count"],
    )
    max_comments_count = _coerce_int(
        raw.get("max_comments_count_singlenotes", raw.get("top_comments_count")),
        DEFAULT_PARAMS["max_comments_count_singlenotes"],
    )
    resolved_keywords = _resolve_keywords(
        raw.get("keywords", raw.get("search_keywords", DEFAULT_PARAMS["keywords"])),
        raw.get("keyword_whitelist", DEFAULT_PARAMS["keyword_whitelist"]),
        raw.get("keyword_blacklist", DEFAULT_PARAMS["keyword_blacklist"]),
        raw.get("scenario_words", DEFAULT_PARAMS["scenario_words"]),
    )
    resolved_accounts = _resolve_accounts(
        raw.get("specified_account_ids", raw.get("creator_ids", DEFAULT_PARAMS["specified_account_ids"])),
        raw.get("account_whitelist", DEFAULT_PARAMS["account_whitelist"]),
        raw.get("account_blacklist", DEFAULT_PARAMS["account_blacklist"]),
    )
    params = {
        "platforms": _normalize_platforms(raw.get("platforms"), DEFAULT_PARAMS["platforms"]),
        "enable_keyword_search": _coerce_bool(raw.get("enable_keyword_search"), DEFAULT_PARAMS["enable_keyword_search"]),
        "keywords": _csv(resolved_keywords),
        "search_keywords": _csv(resolved_keywords),
        "keyword_whitelist": _csv(raw.get("keyword_whitelist", DEFAULT_PARAMS["keyword_whitelist"])),
        "keyword_blacklist": _csv(raw.get("keyword_blacklist", DEFAULT_PARAMS["keyword_blacklist"])),
        "scenario_words": _csv(raw.get("scenario_words", DEFAULT_PARAMS["scenario_words"])),
        "max_notes_count": max_notes_count,
        "max_notes_per_keyword": max_notes_count,
        "enable_comments": _coerce_bool(raw.get("enable_comments"), DEFAULT_PARAMS["enable_comments"]),
        "enable_sub_comments": _coerce_bool(raw.get("enable_sub_comments"), DEFAULT_PARAMS["enable_sub_comments"]),
        "max_comments_count_singlenotes": max_comments_count,
        "top_comments_count": max_comments_count,
        "enable_account_crawl": _coerce_bool(raw.get("enable_account_crawl"), DEFAULT_PARAMS["enable_account_crawl"] or bool(resolved_accounts)),
        "specified_account_ids": _csv(resolved_accounts),
        "creator_ids": _csv(resolved_accounts),
        "account_whitelist": _csv(raw.get("account_whitelist", DEFAULT_PARAMS["account_whitelist"])),
        "account_blacklist": _csv(raw.get("account_blacklist", DEFAULT_PARAMS["account_blacklist"])),
        "min_engagement": _coerce_int(raw.get("min_engagement"), DEFAULT_PARAMS["min_engagement"]),
        "keyword_score_threshold": _coerce_int(raw.get("keyword_score_threshold"), DEFAULT_PARAMS["keyword_score_threshold"]),
    }
    if params["max_notes_count"] < 1:
        raise ValueError("max_notes_count must be greater than 0.")
    if params["max_comments_count_singlenotes"] < 1:
        raise ValueError("max_comments_count_singlenotes must be greater than 0.")
    if params["min_engagement"] < 0:
        raise ValueError("min_engagement must be greater than or equal to 0.")
    if params["keyword_score_threshold"] < 0:
        raise ValueError("keyword_score_threshold must be greater than or equal to 0.")
    if not params["enable_comments"]:
        params["enable_sub_comments"] = False
    if params["enable_keyword_search"] and not params["keywords"]:
        raise ValueError("keywords cannot be empty when keyword search is enabled.")
    if params["enable_account_crawl"] and not params["specified_account_ids"]:
        raise ValueError("specified_account_ids cannot be empty when account crawl is enabled.")
    if not params["enable_keyword_search"] and not params["enable_account_crawl"]:
        raise ValueError("At least one vibe crawl stage must be enabled.")
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    if params is None:
        params = {
            **DEFAULT_PARAMS,
            "platforms": _sanitize_list(os.getenv("VIBE_PLATFORMS", "")) or list(DEFAULT_PARAMS["platforms"]),
            "enable_keyword_search": _coerce_bool(os.getenv("VIBE_ENABLE_KEYWORD_SEARCH"), DEFAULT_PARAMS["enable_keyword_search"]),
            "enable_account_crawl": _coerce_bool(os.getenv("VIBE_ENABLE_ACCOUNT_CRAWL"), DEFAULT_PARAMS["enable_account_crawl"]),
        }
    normalized = normalize_params(params)
    stages: list[TaskStage] = []

    if normalized["enable_keyword_search"]:
        jobs = [
            TaskJob(
                key=f"search_{platform}",
                name=f"{PLATFORM_LABELS.get(platform, platform)} vibe search crawl",
                command=[
                    python_executable,
                    "-m",
                    "vibe_coding.cli",
                    "--enabled",
                    "true",
                    "--platform",
                    platform,
                    "--search-keywords",
                    normalized["keywords"],
                    "--max-notes-per-keyword",
                    str(normalized["max_notes_count"]),
                    "--min-engagement",
                    str(normalized["min_engagement"]),
                ],
                cwd=project_root,
            )
            for platform in normalized["platforms"]
        ]
        stages.append(
            TaskStage(
                key="vibe_keyword_parallel_crawl",
                name="Vibe keyword search crawl",
                jobs=jobs,
                concurrent=True,
                abort_on_failure=False,
            )
        )

    if normalized["enable_account_crawl"]:
        jobs = [
            TaskJob(
                key=f"creator_{platform}",
                name=f"{PLATFORM_LABELS.get(platform, platform)} vibe creator crawl",
                command=[
                    python_executable,
                    "main.py",
                    "--platform",
                    platform,
                    "--type",
                    "creator",
                    "--creator_id",
                    normalized["specified_account_ids"],
                    "--max_notes_count",
                    str(normalized["max_notes_count"]),
                    "--get_comment",
                    "true" if normalized["enable_comments"] else "false",
                    "--get_sub_comment",
                    "true" if normalized["enable_sub_comments"] else "false",
                    "--max_comments_count_singlenotes",
                    str(normalized["max_comments_count_singlenotes"]),
                ],
                cwd=project_root,
            )
            for platform in normalized["platforms"]
        ]
        stages.append(
            TaskStage(
                key="vibe_creator_parallel_crawl",
                name="Vibe creator target crawl",
                jobs=jobs,
                concurrent=True,
                abort_on_failure=False,
            )
        )

    return TaskSpec(
        slug="vibe_coding",
        title="Vibe Coding Radar",
        short_desc="Configurable collection of AI coding trend content",
        capabilities=[
            "Config-driven vibe coding monitoring",
            "Keyword search and creator-target stages",
            "Compatibility with legacy vibe task parameters",
        ],
        welcome_lines=[
            "Mission: discover high-signal vibe coding ideas.",
            f"Keyword search: {'enabled' if normalized['enable_keyword_search'] else 'disabled'}",
            f"Creator crawl: {'enabled' if normalized['enable_account_crawl'] else 'disabled'}",
            f"Keywords: {normalized['keywords'] or 'n/a'}",
            f"Creator IDs: {normalized['specified_account_ids'] or 'n/a'}",
        ],
        stages=stages,
        aliases=["vibe", "idea_radar"],
    )


def build_definition() -> TaskDefinition:
    preset_seeds: list[PresetSeed] = []
    for preset in TASK_CONFIG["presets"]:
        preset_id = str(preset.get("id", "")).strip()
        preset_name = str(preset.get("name", "")).strip()
        if not preset_id or not preset_name:
            continue
        merged = dict(DEFAULT_PARAMS)
        merged.update(dict(preset))
        merged.pop("id", None)
        merged.pop("name", None)
        merged.pop("is_default", None)
        preset_seeds.append(
            PresetSeed(
                id=f"preset_vibe_{preset_id}",
                task_slug="vibe_coding",
                name=preset_name,
                params=normalize_params(merged),
                is_default=_coerce_bool(preset.get("is_default"), False),
            )
        )
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=preset_seeds,
    )
