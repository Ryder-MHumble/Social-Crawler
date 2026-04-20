from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from tasks.common.models import TaskSpec


@dataclass
class TaskFieldOption:
    value: Any
    label: str
    description: str = ""


@dataclass
class TaskField:
    key: str
    component: str
    label: str
    default: Any = None
    description: str = ""
    group: str = "General"
    required: bool = False
    options: list[TaskFieldOption] = field(default_factory=list)
    placeholder: str = ""
    rows: int | None = None
    layout: str = "default"
    helper_text: str = ""
    badge: str = ""
    visible_when: dict[str, Any] | None = None
    disabled_when: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


@dataclass
class PresetSeed:
    id: str
    task_slug: str
    name: str
    params: dict[str, Any]
    is_default: bool = False


NormalizeParamsFn = Callable[[Mapping[str, Any] | None], dict[str, Any]]
BuildTaskSpecFn = Callable[[Path, str, Mapping[str, Any] | None], TaskSpec]


@dataclass
class TaskTemplate:
    slug: str
    title: str
    description: str
    defaults: dict[str, Any]
    fields: list[TaskField]
    capabilities: list[str] = field(default_factory=list)


@dataclass
class TaskDefinition:
    template: TaskTemplate
    normalize_params: NormalizeParamsFn
    build_task_spec: BuildTaskSpecFn
    preset_seeds: list[PresetSeed] = field(default_factory=list)
