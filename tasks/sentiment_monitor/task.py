from __future__ import annotations

import os
from pathlib import Path

import config
from tasks.common.models import TaskJob, TaskSpec, TaskStage

DEFAULT_PLATFORMS = ["xhs", "dy", "bili", "zhihu"]
PLATFORM_NAMES = {
    "xhs": "XiaoHongShu",
    "dy": "Douyin",
    "bili": "Bilibili",
    "zhihu": "Zhihu",
}
PLATFORM_MAX_NOTES = {
    "dy": 10,
    "bili": 15,
    "zhihu": 10,
}


def _split_list(raw: str, fallback: list[str]) -> list[str]:
    if not raw.strip():
        return fallback
    return [item.strip() for item in raw.split(",") if item.strip()]


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


def build_task(project_root: Path, python_executable: str) -> TaskSpec:
    keywords = os.getenv("SENTIMENT_KEYWORDS", getattr(config, "KEYWORDS", ""))
    if not keywords.strip():
        keywords = "AI,crawler,social media"

    save_option = os.getenv("SENTIMENT_SAVE_OPTION", getattr(config, "SAVE_DATA_OPTION", "supabase"))
    get_comment = os.getenv("SENTIMENT_GET_COMMENT", "yes")
    raw_platforms = os.getenv("SENTIMENT_PLATFORMS", "")
    platforms = _split_list(raw_platforms, DEFAULT_PLATFORMS)

    jobs: list[TaskJob] = []
    for platform in platforms:
        cookie = _load_cookie(platform)
        login_type = "cookie" if cookie else os.getenv("SENTIMENT_LOGIN_TYPE", "qrcode")

        cmd = [
            python_executable,
            "main.py",
            "--platform",
            platform,
            "--lt",
            login_type,
            "--type",
            "search",
            "--keywords",
            keywords,
            "--save_data_option",
            save_option,
            "--get_comment",
            get_comment,
        ]

        max_notes = PLATFORM_MAX_NOTES.get(platform)
        if max_notes:
            cmd.extend(["--max_notes_count", str(max_notes)])

        if cookie:
            cmd.extend(["--cookies", cookie])

        jobs.append(
            TaskJob(
                key=platform,
                name=f"{PLATFORM_NAMES.get(platform, platform)} crawl",
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
        f"Platforms: {', '.join(PLATFORM_NAMES.get(p, p) for p in platforms)}",
        f"Storage: {save_option}",
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

