from __future__ import annotations

from pathlib import Path

from tasks.common.models import TaskSpec
from tasks.creator_outreach.task import build_task as build_creator_outreach_task
from tasks.sentiment_monitor.task import build_task as build_sentiment_task
from tasks.vibe_coding.task import build_task as build_vibe_task


def load_task_specs(project_root: Path, python_executable: str) -> list[TaskSpec]:
    return [
        build_sentiment_task(project_root, python_executable),
        build_creator_outreach_task(project_root, python_executable),
        build_vibe_task(project_root, python_executable),
    ]


def resolve_task(task_specs: list[TaskSpec], key: str) -> TaskSpec | None:
    normalized = key.strip().lower().replace("-", "_")
    for spec in task_specs:
        alias_pool = {spec.slug, *spec.aliases}
        normalized_alias_pool = {item.lower().replace("-", "_") for item in alias_pool}
        if normalized in normalized_alias_pool:
            return spec
    return None

