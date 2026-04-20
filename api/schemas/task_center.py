from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskFieldOptionResponse(BaseModel):
    value: Any
    label: str
    description: str = ""


class TaskFieldResponse(BaseModel):
    key: str
    component: str
    label: str
    default: Any = None
    description: str = ""
    group: str = "General"
    required: bool = False
    options: list[TaskFieldOptionResponse] = Field(default_factory=list)
    placeholder: str = ""
    rows: int | None = None
    layout: str = "default"
    helper_text: str = ""
    badge: str = ""
    visible_when: dict[str, Any] | None = None
    disabled_when: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


class TaskTemplateResponse(BaseModel):
    slug: str
    title: str
    description: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    fields: list[TaskFieldResponse] = Field(default_factory=list)


class TaskJobResponse(BaseModel):
    key: str
    name: str
    cwd: str
    command: list[str]
    display_command: str | None = None
    status: str | None = None
    log_path: str | None = None
    exit_code: int | None = None
    line_count: int | None = None
    last_line: str | None = None
    pid: int | None = None
    last_output_at: str | None = None
    last_state_change_at: str | None = None
    watchdog_status: str | None = None
    stall_deadline_at: str | None = None
    termination_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class TaskStageResponse(BaseModel):
    key: str
    name: str
    concurrent: bool
    abort_on_failure: bool
    status: str | None = None
    jobs: list[TaskJobResponse] = Field(default_factory=list)


class TaskPreviewRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    preset_id: str | None = None


class TaskPreviewResponse(BaseModel):
    task: TaskTemplateResponse
    normalized_params: dict[str, Any] = Field(default_factory=dict)
    spec: dict[str, Any]


class TaskPresetResponse(BaseModel):
    id: str
    task_slug: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    updated_at: str


class TaskPresetCreateRequest(BaseModel):
    task_slug: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class TaskPresetUpdateRequest(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class TaskRunStartRequest(BaseModel):
    task_slug: str
    params: dict[str, Any] = Field(default_factory=dict)
    preset_id: str | None = None


class TaskRunResponse(BaseModel):
    id: str
    task_slug: str
    title: str
    status: str
    preset_id: str | None = None
    normalized_params: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    log_path: str | None = None
    metrics: dict[str, int] = Field(default_factory=dict)
    stages: list[TaskStageResponse] = Field(default_factory=list)


class TaskLogEntryResponse(BaseModel):
    id: int
    timestamp: str
    level: str
    message: str
    stage_key: str | None = None
    stage_name: str | None = None
    job_key: str | None = None
    job_name: str | None = None
