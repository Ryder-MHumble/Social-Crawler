from __future__ import annotations

import os
from pathlib import Path

from tasks.common.models import TaskJob, TaskSpec, TaskStage


def _as_bool(raw: str, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _find_discovery_script(project_root: Path) -> Path:
    primary = project_root / "scripts" / "bili_creator_crawler" / "crawl_bili_creators.py"
    return primary


def build_task(project_root: Path, python_executable: str) -> TaskSpec:
    skip_discovery = _as_bool(os.getenv("OUTREACH_SKIP_DISCOVERY", ""), default=False)
    run_filter = _as_bool(os.getenv("OUTREACH_ENABLE_FILTER", "1"), default=True)

    stages: list[TaskStage] = []

    if not skip_discovery:
        discovery_script = _find_discovery_script(project_root)
        discovery_stage = TaskStage(
            key="discover_creators",
            name="Discover creators by keyword",
            jobs=[
                TaskJob(
                    key="discover",
                    name="Creator discovery",
                    command=[python_executable, str(discovery_script)],
                    cwd=project_root,
                )
            ],
            concurrent=False,
            abort_on_failure=True,
        )
        stages.append(discovery_stage)

    prepare_stage = TaskStage(
        key="prepare_creator_list",
        name="Prepare outreach creator list",
        jobs=[
            TaskJob(
                key="prepare_csv",
                name="Prepare creator CSV",
                command=[
                    python_executable,
                    "tasks/creator_outreach/prepare_creator_csv.py",
                    "--filter",
                    "1" if run_filter else "0",
                ],
                cwd=project_root,
            )
        ],
        concurrent=False,
        abort_on_failure=True,
    )
    stages.append(prepare_stage)

    dm_stage = TaskStage(
        key="dm_campaign",
        name="Send outreach DM campaign",
        jobs=[
            TaskJob(
                key="send_dm",
                name="Bilibili DM sender",
                command=[python_executable, "send_bilibili_dm_manual.py"],
                cwd=project_root / "bilibili_dm_sender",
            )
        ],
        concurrent=False,
        abort_on_failure=False,
    )
    stages.append(dm_stage)

    capabilities = [
        "Search creators by target keywords",
        "Prepare one unified outreach CSV list",
        "Run Bilibili private-message campaign (script uses concurrent tabs by default)",
    ]
    welcome_lines = [
        "Mission: discover creators and launch outreach DM campaign.",
        f"Discovery step: {'skip' if skip_discovery else 'run'}",
        f"Noise filter: {'enabled' if run_filter else 'disabled'}",
        "Note: DM sender will request manual Bilibili login in browser.",
    ]

    return TaskSpec(
        slug="creator_outreach",
        title="Creator Outreach",
        short_desc="Keyword search creators and launch DM campaign",
        capabilities=capabilities,
        welcome_lines=welcome_lines,
        stages=stages,
        aliases=["outreach", "dm_campaign"],
    )
