from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskTemplate

DEFAULT_DISCOVERY_KEYWORDS = [
    "openclaw教程",
    "openclaw使用",
    "openclaw",
    "小龙虾编程",
]
DEFAULT_PARAMS = {
    "run_discovery": True,
    "run_filter": True,
    "run_dm": False,
    "discovery_keywords": ",".join(DEFAULT_DISCOVERY_KEYWORDS),
    "max_pages_per_keyword": 3,
    "max_videos_per_creator": 20,
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _find_discovery_script(project_root: Path) -> Path:
    return project_root / "tasks" / "creator_outreach" / "discover_bilibili_creators.py"


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="creator_outreach",
        title="创作者触达",
        description="Bilibili only。第一版只开放发现、过滤、发私信三个阶段开关和最小参数。",
        defaults=dict(DEFAULT_PARAMS),
        capabilities=[
            "固定 Bilibili 流程",
            "阶段级开关，避免误触发私信发送",
            "发现脚本参数可在 UI 中覆盖",
        ],
        fields=[
            TaskField(
                key="run_discovery",
                component="switch",
                label="执行发现阶段",
                default=DEFAULT_PARAMS["run_discovery"],
                group="阶段控制",
            ),
            TaskField(
                key="run_filter",
                component="switch",
                label="执行过滤阶段",
                default=DEFAULT_PARAMS["run_filter"],
                group="阶段控制",
            ),
            TaskField(
                key="run_dm",
                component="switch",
                label="执行私信阶段",
                default=DEFAULT_PARAMS["run_dm"],
                description="默认关闭，避免误发。",
                group="阶段控制",
            ),
            TaskField(
                key="discovery_keywords",
                component="textarea",
                label="发现关键词",
                default=DEFAULT_PARAMS["discovery_keywords"],
                description="多个关键词用英文逗号分隔。",
                group="发现参数",
                visible_when={"run_discovery": True},
            ),
            TaskField(
                key="max_pages_per_keyword",
                component="number",
                label="每个关键词抓取页数",
                default=DEFAULT_PARAMS["max_pages_per_keyword"],
                group="发现参数",
                visible_when={"run_discovery": True},
                validation={"min": 1, "max": 20},
            ),
            TaskField(
                key="max_videos_per_creator",
                component="number",
                label="每个创作者抓取视频数",
                default=DEFAULT_PARAMS["max_videos_per_creator"],
                group="发现参数",
                visible_when={"run_discovery": True},
                validation={"min": 1, "max": 100},
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    params = {
        "run_discovery": _coerce_bool(raw.get("run_discovery"), DEFAULT_PARAMS["run_discovery"]),
        "run_filter": _coerce_bool(raw.get("run_filter"), DEFAULT_PARAMS["run_filter"]),
        "run_dm": _coerce_bool(raw.get("run_dm"), DEFAULT_PARAMS["run_dm"]),
        "discovery_keywords": str(
            raw.get("discovery_keywords", DEFAULT_PARAMS["discovery_keywords"])
        ).strip(),
        "max_pages_per_keyword": int(
            raw.get("max_pages_per_keyword", DEFAULT_PARAMS["max_pages_per_keyword"])
        ),
        "max_videos_per_creator": int(
            raw.get("max_videos_per_creator", DEFAULT_PARAMS["max_videos_per_creator"])
        ),
    }
    if not (params["run_discovery"] or params["run_filter"] or params["run_dm"]):
        raise ValueError("At least one stage must be enabled.")
    if params["run_discovery"] and not params["discovery_keywords"]:
        raise ValueError("discovery_keywords cannot be empty when discovery is enabled.")
    if params["max_pages_per_keyword"] < 1:
        raise ValueError("max_pages_per_keyword must be greater than 0.")
    if params["max_videos_per_creator"] < 1:
        raise ValueError("max_videos_per_creator must be greater than 0.")
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    if params is None:
        skip_discovery = _coerce_bool(os.getenv("OUTREACH_SKIP_DISCOVERY", ""), default=False)
        run_filter = _coerce_bool(os.getenv("OUTREACH_ENABLE_FILTER", "1"), default=True)
        stages: list[TaskStage] = []
        if not skip_discovery:
            discovery_script = _find_discovery_script(project_root)
            stages.append(
                TaskStage(
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
            )
        stages.append(
            TaskStage(
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
        )
        stages.append(
            TaskStage(
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
        )
        welcome_lines = [
            "Mission: discover creators and launch outreach DM campaign.",
            f"Discovery step: {'skip' if skip_discovery else 'run'}",
            f"Noise filter: {'enabled' if run_filter else 'disabled'}",
            "Note: DM sender will request manual Bilibili login in browser.",
        ]
    else:
        normalized = normalize_params(params)
        stages = []
        discovery_script = _find_discovery_script(project_root)
        if normalized["run_discovery"]:
            stages.append(
                TaskStage(
                    key="discover_creators",
                    name="Discover creators by keyword",
                    jobs=[
                        TaskJob(
                            key="discover",
                            name="Creator discovery",
                            command=[
                                python_executable,
                                str(discovery_script),
                                "--keywords",
                                normalized["discovery_keywords"],
                                "--max-pages-per-keyword",
                                str(normalized["max_pages_per_keyword"]),
                                "--max-videos-per-creator",
                                str(normalized["max_videos_per_creator"]),
                            ],
                            cwd=project_root,
                        )
                    ],
                    concurrent=False,
                    abort_on_failure=True,
                )
            )
        if normalized["run_filter"]:
            stages.append(
                TaskStage(
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
                                "1",
                            ],
                            cwd=project_root,
                        )
                    ],
                    concurrent=False,
                    abort_on_failure=True,
                )
            )
        if normalized["run_dm"]:
            stages.append(
                TaskStage(
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
            )
        welcome_lines = [
            "Mission: run the Bilibili creator outreach workflow.",
            f"Discovery: {'on' if normalized['run_discovery'] else 'off'}",
            f"Filter: {'on' if normalized['run_filter'] else 'off'}",
            f"DM: {'on' if normalized['run_dm'] else 'off'}",
        ]

    capabilities = [
        "Bilibili-only creator discovery and outreach",
        "Discovery script now accepts runtime keyword/page/video overrides",
        "DM stage remains opt-in",
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


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id="preset_creator_discovery_only",
                task_slug="creator_outreach",
                name="创作者发现-不发私信",
                params=dict(DEFAULT_PARAMS),
                is_default=False,
            )
        ],
    )
