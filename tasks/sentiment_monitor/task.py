from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import config
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
LOGIN_OPTIONS = [
    TaskFieldOption(value="qrcode", label="二维码登录"),
    TaskFieldOption(value="cookie", label="Cookie 登录"),
    TaskFieldOption(value="phone", label="手机号登录"),
]
SAVE_OPTIONS = [
    TaskFieldOption(value="json", label="JSON (Local Default)"),
    TaskFieldOption(value="csv", label="CSV"),
    TaskFieldOption(value="excel", label="Excel"),
    TaskFieldOption(value="sqlite", label="SQLite (Extension)"),
    TaskFieldOption(value="db", label="MySQL (Extension)"),
    TaskFieldOption(value="mongodb", label="MongoDB (Extension)"),
    TaskFieldOption(value="supabase", label="Supabase (Extension)"),
]
UI_DEFAULT_PARAMS = {
    "platforms": ["xhs"],
    "keywords": getattr(config, "KEYWORDS", ""),
    "max_notes_count": 30,
    "enable_comments": False,
    "enable_sub_comments": False,
    "max_comments_count_singlenotes": getattr(config, "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES", 20),
    "login_type": getattr(config, "LOGIN_TYPE", "qrcode"),
    "save_option": getattr(config, "SAVE_DATA_OPTION", "json"),
    "headless": getattr(config, "HEADLESS", False),
}
LEGACY_PLATFORM_MAX_NOTES = {
    "dy": 10,
    "bili": 15,
    "zhihu": 10,
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_list(raw: str, fallback: list[str]) -> list[str]:
    if not raw.strip():
        return list(fallback)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_platforms(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        platforms = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        platforms = _split_list(value, fallback)
    else:
        platforms = list(fallback)
    valid_platforms = [platform for platform in platforms if platform in PLATFORM_LABELS]
    return valid_platforms or list(fallback)


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


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="sentiment_monitor",
        title="舆情监控",
        description="按平台和关键词运行内容抓取任务，第一版优先支持小红书纯帖子采集。",
        defaults=dict(UI_DEFAULT_PARAMS),
        capabilities=[
            "多平台关键词搜索",
            "评论与二级评论可配",
            "运行前可预览解析出的实际命令",
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
                key="keywords",
                component="textarea",
                label="关键词",
                default=UI_DEFAULT_PARAMS["keywords"],
                description="多个关键词用英文逗号分隔。",
                group="采集范围",
                required=True,
                validation={"min_length": 1},
            ),
            TaskField(
                key="max_notes_count",
                component="number",
                label="每个平台抓取条数",
                default=UI_DEFAULT_PARAMS["max_notes_count"],
                group="内容控制",
                validation={"min": 1, "max": 200},
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
                label="每条内容评论数上限",
                default=UI_DEFAULT_PARAMS["max_comments_count_singlenotes"],
                group="内容控制",
                visible_when={"enable_comments": True},
                validation={"min": 1, "max": 200},
            ),
            TaskField(
                key="login_type",
                component="select",
                label="登录方式",
                default=UI_DEFAULT_PARAMS["login_type"],
                group="运行配置",
                options=LOGIN_OPTIONS,
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
                key="headless",
                component="switch",
                label="无头模式",
                default=UI_DEFAULT_PARAMS["headless"],
                group="运行配置",
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    params = {
        "platforms": _normalize_platforms(raw.get("platforms"), UI_DEFAULT_PARAMS["platforms"]),
        "keywords": str(raw.get("keywords", UI_DEFAULT_PARAMS["keywords"])).strip(),
        "max_notes_count": int(raw.get("max_notes_count", UI_DEFAULT_PARAMS["max_notes_count"])),
        "enable_comments": _coerce_bool(raw.get("enable_comments"), UI_DEFAULT_PARAMS["enable_comments"]),
        "enable_sub_comments": _coerce_bool(
            raw.get("enable_sub_comments"),
            UI_DEFAULT_PARAMS["enable_sub_comments"],
        ),
        "max_comments_count_singlenotes": int(
            raw.get(
                "max_comments_count_singlenotes",
                UI_DEFAULT_PARAMS["max_comments_count_singlenotes"],
            )
        ),
        "login_type": str(raw.get("login_type", UI_DEFAULT_PARAMS["login_type"])).strip() or "qrcode",
        "save_option": str(raw.get("save_option", UI_DEFAULT_PARAMS["save_option"])).strip() or "json",
        "headless": _coerce_bool(raw.get("headless"), UI_DEFAULT_PARAMS["headless"]),
    }
    if not params["keywords"]:
        raise ValueError("Keywords cannot be empty.")
    if params["max_notes_count"] < 1:
        raise ValueError("max_notes_count must be greater than 0.")
    if params["max_comments_count_singlenotes"] < 1:
        raise ValueError("max_comments_count_singlenotes must be greater than 0.")
    if not params["enable_comments"]:
        params["enable_sub_comments"] = False
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    if params is None:
        keywords = os.getenv("SENTIMENT_KEYWORDS", getattr(config, "KEYWORDS", ""))
        if not keywords.strip():
            keywords = getattr(config, "KEYWORDS", "编程副业,编程兼职")

        save_option = os.getenv(
            "SENTIMENT_SAVE_OPTION",
            getattr(config, "SAVE_DATA_OPTION", "json"),
        )
        get_comment = os.getenv("SENTIMENT_GET_COMMENT", "yes")
        raw_platforms = os.getenv("SENTIMENT_PLATFORMS", "")
        platforms = _split_list(raw_platforms, DEFAULT_PLATFORMS)
        login_type = os.getenv("SENTIMENT_LOGIN_TYPE", "qrcode")
        jobs: list[TaskJob] = []
        for platform in platforms:
            cookie = _load_cookie(platform)
            runtime_login_type = "cookie" if cookie else login_type
            cmd = [
                python_executable,
                "main.py",
                "--platform",
                platform,
                "--lt",
                runtime_login_type,
                "--type",
                "search",
                "--keywords",
                keywords,
                "--save_data_option",
                save_option,
                "--get_comment",
                get_comment,
            ]
            max_notes = LEGACY_PLATFORM_MAX_NOTES.get(platform)
            if max_notes:
                cmd.extend(["--max_notes_count", str(max_notes)])
            if cookie:
                cmd.extend(["--cookies", cookie])
            jobs.append(
                TaskJob(
                    key=platform,
                    name=f"{PLATFORM_LABELS.get(platform, platform)} crawl",
                    command=cmd,
                    cwd=project_root,
                )
            )
        capabilities = [
            "Multi-platform sentiment monitoring",
            "Default parallel crawling across all selected platforms",
            "Unified storage output and live job logs",
        ]
        welcome_lines = [
            "Mission: monitor social sentiment with one command.",
            f"Keywords: {keywords}",
            f"Platforms: {', '.join(PLATFORM_LABELS.get(p, p) for p in platforms)}",
            f"Storage: {save_option}",
        ]
    else:
        normalized = normalize_params(params)
        jobs = []
        for platform in normalized["platforms"]:
            cmd = [
                python_executable,
                "main.py",
                "--platform",
                platform,
                "--lt",
                normalized["login_type"],
                "--type",
                "search",
                "--keywords",
                normalized["keywords"],
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
            cookie = _load_cookie(platform) if normalized["login_type"] == "cookie" else ""
            if cookie:
                cmd.extend(["--cookies", cookie])
            jobs.append(
                TaskJob(
                    key=platform,
                    name=f"{PLATFORM_LABELS.get(platform, platform)} crawl",
                    command=cmd,
                    cwd=project_root,
                )
            )
        capabilities = [
            "Task-template driven sentiment monitoring",
            "Platform / keyword / comment parameters are editable at runtime",
            "Optimized for the XiaoHongShu post-only workflow",
        ]
        welcome_lines = [
            "Mission: run configurable sentiment monitoring.",
            f"Keywords: {normalized['keywords']}",
            f"Platforms: {', '.join(PLATFORM_LABELS.get(p, p) for p in normalized['platforms'])}",
            f"Comments: {'enabled' if normalized['enable_comments'] else 'disabled'}",
            f"Save option: {normalized['save_option']}",
        ]

    stage = TaskStage(
        key="sentiment_parallel_crawl",
        name="Sentiment parallel crawl",
        jobs=jobs,
        concurrent=True,
        abort_on_failure=False,
    )
    return TaskSpec(
        slug="sentiment_monitor",
        title="Sentiment Monitor",
        short_desc="Parallel sentiment crawl across social platforms",
        capabilities=capabilities,
        welcome_lines=welcome_lines,
        stages=[stage],
        aliases=["sentiment", "monitor"],
    )


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id="preset_sentiment_xhs_posts_only",
                task_slug="sentiment_monitor",
                name="小红书舆情-纯帖子版",
                params={
                    "platforms": ["xhs"],
                    "keywords": getattr(config, "KEYWORDS", ""),
                    "max_notes_count": 30,
                    "enable_comments": False,
                    "enable_sub_comments": False,
                    "max_comments_count_singlenotes": getattr(
                        config,
                        "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES",
                        20,
                    ),
                    "login_type": getattr(config, "LOGIN_TYPE", "qrcode"),
                    "save_option": getattr(config, "SAVE_DATA_OPTION", "supabase"),
                    "headless": getattr(config, "HEADLESS", False),
                },
                is_default=True,
            ),
            PresetSeed(
                id="preset_sentiment_multi_platform",
                task_slug="sentiment_monitor",
                name="多平台舆情-含评论",
                params={
                    "platforms": ["xhs", "dy", "bili"],
                    "keywords": getattr(config, "KEYWORDS", ""),
                    "max_notes_count": 20,
                    "enable_comments": True,
                    "enable_sub_comments": False,
                    "max_comments_count_singlenotes": 20,
                    "login_type": getattr(config, "LOGIN_TYPE", "qrcode"),
                    "save_option": getattr(config, "SAVE_DATA_OPTION", "supabase"),
                    "headless": getattr(config, "HEADLESS", False),
                },
                is_default=False,
            ),
        ],
    )
