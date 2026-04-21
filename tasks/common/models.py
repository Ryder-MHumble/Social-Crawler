from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskJob:
    key: str
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskStage:
    key: str
    name: str
    jobs: list[TaskJob]
    concurrent: bool = True
    max_parallel: int | None = None
    abort_on_failure: bool = False


@dataclass
class TaskSpec:
    slug: str
    title: str
    short_desc: str
    capabilities: list[str]
    welcome_lines: list[str]
    stages: list[TaskStage]
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
