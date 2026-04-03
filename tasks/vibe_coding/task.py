from __future__ import annotations

import os
from pathlib import Path

from tasks.common.models import TaskJob, TaskSpec, TaskStage
import vibe_coding.config as vc_cfg

PLATFORM_NAMES = {
    "xhs": "XiaoHongShu",
    "bili": "Bilibili",
    "dy": "Douyin",
    "wb": "Weibo",
}


def _split_list(raw: str, fallback: list[str]) -> list[str]:
    if not raw.strip():
        return fallback
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_task(project_root: Path, python_executable: str) -> TaskSpec:
    configured_platforms = list(getattr(vc_cfg, "VIBE_CODING_PLATFORMS", ["xhs", "bili"]))
    platforms = _split_list(os.getenv("VIBE_PLATFORMS", ""), configured_platforms)

    jobs = [
        TaskJob(
            key=platform,
            name=f"{PLATFORM_NAMES.get(platform, platform)} vibe crawl",
            command=[python_executable, "run_vibe_coding.py", "--platform", platform],
            cwd=project_root,
        )
        for platform in platforms
    ]

    enabled_text = "enabled" if vc_cfg.ENABLE_VIBE_CODING_COLLECTION else "disabled"
    capabilities = [
        "Collect vibe-coding trend content",
        "Default parallel crawling across configured platforms",
        "Reuse unified progress monitor and final report",
    ]
    welcome_lines = [
        "Mission: discover high-signal vibe coding ideas.",
        f"Collection switch: {enabled_text}",
        f"Platforms: {', '.join(PLATFORM_NAMES.get(p, p) for p in platforms)}",
        f"Keyword score threshold: {vc_cfg.KEYWORD_SCORE_THRESHOLD}",
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

