from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
DEFAULT_PARAMS = {
    "platforms": list(getattr(vc_cfg, "VIBE_CODING_PLATFORMS", ["xhs", "bili"])),
    "search_keywords": ",".join(getattr(vc_cfg, "SEARCH_KEYWORDS", [])),
    "max_notes_per_keyword": getattr(vc_cfg, "VIBE_CODING_MAX_NOTES_PER_KEYWORD", 20),
    "min_engagement": getattr(vc_cfg, "VIBE_CODING_MIN_ENGAGEMENT", 5),
}


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


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="vibe_coding",
        title="Vibe Coding 雷达",
        description="抓取 AI 编程趋势内容，第一版只开放平台、搜索词、条数和最低互动量。",
        defaults=dict(DEFAULT_PARAMS),
        capabilities=[
            "聚焦高信号 AI Coding 主题",
            "运行时覆盖搜索词和阈值",
            "AI 分析开关在 v1 中保持隐藏",
        ],
        fields=[
            TaskField(
                key="platforms",
                component="multiselect",
                label="平台",
                default=list(DEFAULT_PARAMS["platforms"]),
                group="采集范围",
                required=True,
                options=PLATFORM_OPTIONS,
                validation={"min_items": 1},
            ),
            TaskField(
                key="search_keywords",
                component="textarea",
                label="搜索词",
                default=DEFAULT_PARAMS["search_keywords"],
                description="多个搜索词用英文逗号分隔。",
                group="采集范围",
                required=True,
                validation={"min_length": 1},
            ),
            TaskField(
                key="max_notes_per_keyword",
                component="number",
                label="每个搜索词抓取条数",
                default=DEFAULT_PARAMS["max_notes_per_keyword"],
                group="筛选阈值",
                validation={"min": 1, "max": 100},
            ),
            TaskField(
                key="min_engagement",
                component="number",
                label="最低互动量",
                default=DEFAULT_PARAMS["min_engagement"],
                group="筛选阈值",
                validation={"min": 0, "max": 100000},
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    params = {
        "platforms": _normalize_platforms(raw.get("platforms"), DEFAULT_PARAMS["platforms"]),
        "search_keywords": str(raw.get("search_keywords", DEFAULT_PARAMS["search_keywords"])).strip(),
        "max_notes_per_keyword": int(
            raw.get("max_notes_per_keyword", DEFAULT_PARAMS["max_notes_per_keyword"])
        ),
        "min_engagement": int(raw.get("min_engagement", DEFAULT_PARAMS["min_engagement"])),
    }
    if not params["search_keywords"]:
        raise ValueError("search_keywords cannot be empty.")
    if params["max_notes_per_keyword"] < 1:
        raise ValueError("max_notes_per_keyword must be greater than 0.")
    if params["min_engagement"] < 0:
        raise ValueError("min_engagement must be greater than or equal to 0.")
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    if params is None:
        configured_platforms = list(getattr(vc_cfg, "VIBE_CODING_PLATFORMS", ["xhs", "bili"]))
        platforms = _split_list(os.getenv("VIBE_PLATFORMS", ""), configured_platforms)
        welcome_lines = [
            "Mission: discover high-signal vibe coding ideas.",
            f"Collection switch: {'enabled' if vc_cfg.ENABLE_VIBE_CODING_COLLECTION else 'disabled'}",
            f"Platforms: {', '.join(PLATFORM_LABELS.get(p, p) for p in platforms)}",
            f"Keyword score threshold: {vc_cfg.KEYWORD_SCORE_THRESHOLD}",
        ]
        jobs = [
            TaskJob(
                key=platform,
                name=f"{PLATFORM_LABELS.get(platform, platform)} vibe crawl",
                command=[python_executable, "-m", "vibe_coding.cli", "--platform", platform],
                cwd=project_root,
            )
            for platform in platforms
        ]
    else:
        normalized = normalize_params(params)
        base_command = [
            python_executable,
            "-m",
            "vibe_coding.cli",
            "--enabled",
            "true",
            "--search-keywords",
            normalized["search_keywords"],
            "--max-notes-per-keyword",
            str(normalized["max_notes_per_keyword"]),
            "--min-engagement",
            str(normalized["min_engagement"]),
        ]
        jobs = [
            TaskJob(
                key=platform,
                name=f"{PLATFORM_LABELS.get(platform, platform)} vibe crawl",
                command=[*base_command, "--platform", platform],
                cwd=project_root,
            )
            for platform in normalized["platforms"]
        ]
        welcome_lines = [
            "Mission: discover high-signal vibe coding ideas.",
            f"Platforms: {', '.join(PLATFORM_LABELS.get(p, p) for p in normalized['platforms'])}",
            f"Search keywords: {normalized['search_keywords']}",
            f"Min engagement: {normalized['min_engagement']}",
        ]

    capabilities = [
        "Collect vibe-coding trend content",
        "Parallel crawl across selected platforms",
        "Runtime keyword and threshold overrides",
    ]
    stage = TaskStage(
        key="vibe_parallel_crawl",
        name="Vibe coding parallel crawl",
        jobs=jobs,
        concurrent=True,
        abort_on_failure=False,
    )
    return TaskSpec(
        slug="vibe_coding",
        title="Vibe Coding Radar",
        short_desc="Parallel collection of AI coding trend content",
        capabilities=capabilities,
        welcome_lines=welcome_lines,
        stages=[stage],
        aliases=["vibe", "idea_radar"],
    )


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id="preset_vibe_xhs_bili",
                task_slug="vibe_coding",
                name="Vibe Radar-双平台默认版",
                params=dict(DEFAULT_PARAMS),
                is_default=False,
            )
        ],
    )
