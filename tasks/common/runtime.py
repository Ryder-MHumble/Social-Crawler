from __future__ import annotations

import ast
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections import deque
from copy import deepcopy
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from database.sqlite_storage import WATCHDOG_DEFAULTS, get_sqlite_storage
from tasks.common.models import TaskJob, TaskSpec, TaskStage

RuntimeEventHandler = Callable[[dict[str, Any]], None]

_SYSTEM_STAGE_KEY = "__system__"
_SYSTEM_STAGE_NAME = "Run Lifecycle"
_SYSTEM_JOB_KEY = "preflight"
_SYSTEM_JOB_NAME = "Run Preflight"

_TIMESTAMP_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s+")
_HEX_RE = re.compile(r"\b[a-f0-9]{8,}\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\b\d+\b")
_NOTE_DETAILS_RE = re.compile(r"Note details:\s*(\[.*\])")
_ISSUE_CODE_RE = re.compile(r"\[issue:([a-z0-9_]+)\]", re.IGNORECASE)


class RunSetupError(RuntimeError):
    def __init__(self, message: str, *, status: str = "failed", level: str = "error") -> None:
        super().__init__(message)
        self.status = status
        self.level = level


def _default_runtime_metrics() -> dict[str, int]:
    return {
        "candidate_count": 0,
        "detail_requests": 0,
        "detail_successes": 0,
        "detail_failures": 0,
        "watchdog_stalls": 0,
        "job_failures": 0,
        "user_stops": 0,
        "degraded_jobs": 0,
    }


def _default_lifecycle() -> dict[str, Any]:
    return {
        "phase": "queued",
        "label": "Queued",
        "detail": "",
        "updated_at": None,
        "current_stage_key": None,
        "current_stage_name": None,
        "stage_index": 0,
        "stage_total": 0,
        "preflight_steps": [],
    }


def _default_job_metrics() -> dict[str, int]:
    return {
        "detail_requests": 0,
        "detail_successes": 0,
        "detail_failures": 0,
    }


@dataclass
class JobRuntime:
    job: TaskJob
    log_path: Path
    status: str = "waiting"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    exit_code: Optional[int] = None
    line_count: int = 0
    last_line: str = ""
    last_output_at: Optional[float] = None
    last_state_change_at: Optional[float] = None
    watchdog_status: str = "idle"
    stall_deadline_at: Optional[float] = None
    termination_reason: str = ""
    termination_requested_at: Optional[float] = None
    process: Optional[subprocess.Popen] = None
    reader_thread: Optional[threading.Thread] = None
    log_fp: Optional[object] = None
    runtime_metrics: dict[str, int] = field(default_factory=_default_job_metrics)
    watchdog_triggered: bool = False


@dataclass
class StageRuntime:
    stage: TaskStage
    jobs: list[JobRuntime]
    status: str = "waiting"


@dataclass
class TaskRunContext:
    run_id: str
    task: TaskSpec
    run_dir: Path
    log_stream_path: Path
    normalized_params: dict[str, Any]
    preset_id: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    status: str = "running"
    interrupted: bool = False
    stages: list[StageRuntime] = field(default_factory=list)
    log_entries: list[dict[str, Any]] = field(default_factory=list)
    next_log_id: int = 1
    lifecycle: dict[str, Any] = field(default_factory=_default_lifecycle)
    issue_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_metrics: dict[str, int] = field(default_factory=_default_runtime_metrics)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def _normalize_issue_fingerprint(message: str) -> str:
    normalized = _TIMESTAMP_PREFIX_RE.sub("", str(message or "").strip().lower())
    normalized = normalized.replace("<token hidden>", "<token>")
    normalized = _HEX_RE.sub("<id>", normalized)
    normalized = _NUMBER_RE.sub("<n>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized[:320] or "unknown"


def _classify_issue(message: str) -> tuple[str, str, str]:
    text = str(message or "").lower()
    explicit = _ISSUE_CODE_RE.search(text)
    if explicit:
        issue_code = explicit.group(1)
        issue_catalog = {
            "browsermint_session_contention": (
                "browsermint_session_contention",
                "BrowserMint 会话争抢",
                "单会话被多个 job 争用，建议强制串行或改成单 worker 内顺序执行。",
            ),
            "detail_token_missing": (
                "detail_token_missing",
                "详情 token/source 缺失",
                "请在进入详情链路前补齐 xsec_source / xsec_token，缺失时回退到 pc_search。",
            ),
            "official_account_token_missing": (
                "official_account_token_missing",
                "官方号 token 缺失",
                "请先解析 profile_url / creator token，再调用 user_posted 等接口。",
            ),
            "preflight_runtime_mismatch": (
                "preflight_runtime_mismatch",
                "预检与真实运行不一致",
                "预检需要覆盖真实搜索/详情读取能力，不能只检查连通性。",
            ),
            "detail_failure_ratio_high": (
                "detail_failure_ratio_high",
                "详情失败率过高",
                "详情成功率过低，建议检查 token/source、登录态与浏览器 fallback 链路。",
            ),
        }
        if issue_code in issue_catalog:
            return issue_catalog[issue_code]
    if re.search(r"timeout|timed out|page\.goto", text):
        return ("timeout", "页面超时", "网络慢或站点响应慢，建议降并发或延长超时。")
    if "failed to get note detail after api and html fallback" in text:
        return ("detail_fallback", "详情抓取失败", "API 与 HTML 回退都失败，通常是风控或内容不可见。")
    if re.search(r"login|cookie|session|qrcode|unauthorized|401|forbidden|403", text):
        return ("auth", "登录/权限问题", "请检查登录态、Cookie 或 BrowserMint 会话有效性。")
    if re.search(r"captcha|risk|rate limit|too many|429|风控|验证码", text):
        return ("risk", "频控/风控", "请求过快或会话风险过高，建议降速或切换会话。")
    if re.search(r"net::|network|dns|econn|proxy|connection", text):
        return ("network", "网络连接问题", "请检查网络、代理与目标站点可达性。")
    return ("other", "其他异常", "需要结合原始日志进一步定位。")


def generate_run_id(prefix: str = "run") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def _append_warning(context: TaskRunContext, warning: dict[str, Any]) -> None:
    code = str(warning.get("code") or "").strip()
    stage_key = str(warning.get("stage_key") or "").strip()
    job_key = str(warning.get("job_key") or "").strip()
    dedupe_key = (code, stage_key, job_key)
    for item in context.warnings:
        existing = (
            str(item.get("code") or "").strip(),
            str(item.get("stage_key") or "").strip(),
            str(item.get("job_key") or "").strip(),
        )
        if existing == dedupe_key:
            item.update({k: v for k, v in warning.items() if v is not None})
            return
    context.warnings.append(dict(warning))


def _serialize_progress(context: TaskRunContext) -> dict[str, Any]:
    stages_payload: list[dict[str, Any]] = []
    total_jobs = 0
    completed_jobs = 0
    running_jobs = 0
    waiting_jobs = 0
    failed_jobs = 0
    degraded_jobs = 0
    stopped_jobs = 0
    skipped_jobs = 0
    current_job: dict[str, Any] | None = None

    for stage_runtime in context.stages:
        stage_total = len(stage_runtime.jobs)
        stage_completed = 0
        stage_running = 0
        stage_waiting = 0
        stage_failed = 0
        stage_degraded = 0
        stage_stopped = 0
        stage_skipped = 0
        slices: list[dict[str, Any]] = []
        for job_runtime in stage_runtime.jobs:
            total_jobs += 1
            status = str(job_runtime.status or "waiting")
            if status in {"success", "failed", "degraded", "stopped", "skipped"}:
                completed_jobs += 1
                stage_completed += 1
            if status == "running":
                running_jobs += 1
                stage_running += 1
                if current_job is None:
                    current_job = {
                        "stage_key": stage_runtime.stage.key,
                        "stage_name": stage_runtime.stage.name,
                        "job_key": job_runtime.job.key,
                        "job_name": job_runtime.job.name,
                        "platform": job_runtime.job.metadata.get("platform"),
                        "platform_label": job_runtime.job.metadata.get("platform_label"),
                        "crawl_type": job_runtime.job.metadata.get("crawl_type"),
                        "slice_kind": job_runtime.job.metadata.get("slice_kind"),
                        "values": list(job_runtime.job.metadata.get("values") or []),
                    }
            elif status == "waiting":
                waiting_jobs += 1
                stage_waiting += 1
            elif status == "failed":
                failed_jobs += 1
                stage_failed += 1
            elif status == "degraded":
                degraded_jobs += 1
                stage_degraded += 1
            elif status == "stopped":
                stopped_jobs += 1
                stage_stopped += 1
            elif status == "skipped":
                skipped_jobs += 1
                stage_skipped += 1

            slices.append(
                {
                    "job_key": job_runtime.job.key,
                    "job_name": job_runtime.job.name,
                    "status": status,
                    "platform": job_runtime.job.metadata.get("platform"),
                    "platform_label": job_runtime.job.metadata.get("platform_label"),
                    "crawl_type": job_runtime.job.metadata.get("crawl_type"),
                    "slice_kind": job_runtime.job.metadata.get("slice_kind"),
                    "slice_label": job_runtime.job.metadata.get("slice_label"),
                    "values": list(job_runtime.job.metadata.get("values") or []),
                    "group_index": job_runtime.job.metadata.get("group_index"),
                    "group_total": job_runtime.job.metadata.get("group_total"),
                }
            )
        stages_payload.append(
            {
                "stage_key": stage_runtime.stage.key,
                "stage_name": stage_runtime.stage.name,
                "status": stage_runtime.status,
                "total_jobs": stage_total,
                "completed_jobs": stage_completed,
                "running_jobs": stage_running,
                "waiting_jobs": stage_waiting,
                "failed_jobs": stage_failed,
                "degraded_jobs": stage_degraded,
                "stopped_jobs": stage_stopped,
                "skipped_jobs": stage_skipped,
                "max_parallel": stage_runtime.stage.max_parallel,
                "concurrent": stage_runtime.stage.concurrent,
                "slices": slices,
            }
        )

    return {
        "summary": {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "running_jobs": running_jobs,
            "waiting_jobs": waiting_jobs,
            "failed_jobs": failed_jobs,
            "degraded_jobs": degraded_jobs,
            "stopped_jobs": stopped_jobs,
            "skipped_jobs": skipped_jobs,
        },
        "current": current_job,
        "stages": stages_payload,
        "preflight_steps": deepcopy(context.lifecycle.get("preflight_steps") or []),
    }


def serialize_run_context(context: TaskRunContext) -> dict[str, Any]:
    storage = get_sqlite_storage()
    sqlite_metrics = storage.get_run_metrics(context.run_id)
    sqlite_breakdowns = storage.get_run_breakdowns(context.run_id)
    watchdog_stalls = sum(
        1
        for stage_runtime in context.stages
        for job_runtime in stage_runtime.jobs
        if job_runtime.watchdog_triggered
    )
    job_failures = sum(
        1
        for stage_runtime in context.stages
        for job_runtime in stage_runtime.jobs
        if job_runtime.status == "failed"
    )
    degraded_jobs = sum(
        1
        for stage_runtime in context.stages
        for job_runtime in stage_runtime.jobs
        if job_runtime.status == "degraded"
    )
    user_stops = sum(
        1
        for stage_runtime in context.stages
        for job_runtime in stage_runtime.jobs
        if job_runtime.status == "stopped"
    )
    effective_save_option = str(
        context.task.metadata.get("effective_save_option")
        or context.normalized_params.get("save_option")
        or ""
    )
    runtime_storage_backend = str(
        context.task.metadata.get("runtime_storage_backend")
        or effective_save_option
    )
    return {
        "id": context.run_id,
        "task_slug": context.task.slug,
        "title": context.task.title,
        "status": context.status,
        "preset_id": context.preset_id,
        "normalized_params": context.normalized_params,
        "started_at": datetime.fromtimestamp(context.started_at).isoformat(),
        "finished_at": (
            datetime.fromtimestamp(context.finished_at).isoformat()
            if context.finished_at
            else None
        ),
        "log_path": str(context.log_stream_path),
        "metrics": {
            **sqlite_metrics,
            "stalled_jobs": watchdog_stalls,
            "candidate_count": max(
                int(context.runtime_metrics.get("candidate_count", 0)),
                int(sqlite_metrics.get("accepted", 0))
                + int(sqlite_metrics.get("filtered", 0))
                + int(sqlite_metrics.get("deduped", 0))
                + int(sqlite_metrics.get("errors", 0)),
            ),
            "detail_requests": int(context.runtime_metrics.get("detail_requests", 0)),
            "detail_successes": int(context.runtime_metrics.get("detail_successes", 0)),
            "detail_failures": int(context.runtime_metrics.get("detail_failures", 0)),
            "watchdog_stalls": watchdog_stalls,
            "job_failures": job_failures,
            "user_stops": user_stops,
            "degraded_jobs": degraded_jobs,
        },
        "lifecycle": dict(context.lifecycle),
        "progress": _serialize_progress(context),
        "warnings": [dict(item) for item in context.warnings],
        "effective_plan": deepcopy(context.task.metadata.get("effective_plan") or {}),
        "effective_save_option": effective_save_option,
        "runtime_storage_backend": runtime_storage_backend,
        "issues": sorted(
            (dict(item) for item in context.issue_summaries.values()),
            key=lambda item: (-int(item.get("count", 0)), str(item.get("last_seen_at", ""))),
        )[:20],
        "breakdowns": sqlite_breakdowns,
        "stages": [
            {
                "key": runtime.stage.key,
                "name": runtime.stage.name,
                "concurrent": runtime.stage.concurrent,
                "max_parallel": runtime.stage.max_parallel,
                "abort_on_failure": runtime.stage.abort_on_failure,
                "status": runtime.status,
                "jobs": [
                    {
                        "key": job_runtime.job.key,
                        "name": job_runtime.job.name,
                        "status": job_runtime.status,
                        "cwd": str(job_runtime.job.cwd),
                        "command": list(job_runtime.job.command),
                        "log_path": str(job_runtime.log_path),
                        "exit_code": job_runtime.exit_code,
                        "line_count": job_runtime.line_count,
                        "last_line": job_runtime.last_line,
                        "pid": job_runtime.process.pid if job_runtime.process else None,
                        "last_output_at": (
                            datetime.fromtimestamp(job_runtime.last_output_at).isoformat()
                            if job_runtime.last_output_at
                            else None
                        ),
                        "last_state_change_at": (
                            datetime.fromtimestamp(job_runtime.last_state_change_at).isoformat()
                            if job_runtime.last_state_change_at
                            else None
                        ),
                        "watchdog_status": job_runtime.watchdog_status,
                        "stall_deadline_at": (
                            datetime.fromtimestamp(job_runtime.stall_deadline_at).isoformat()
                            if job_runtime.stall_deadline_at
                            else None
                        ),
                        "termination_reason": job_runtime.termination_reason or None,
                        "started_at": (
                            datetime.fromtimestamp(job_runtime.started_at).isoformat()
                            if job_runtime.started_at
                            else None
                        ),
                        "finished_at": (
                            datetime.fromtimestamp(job_runtime.finished_at).isoformat()
                            if job_runtime.finished_at
                            else None
                        ),
                        "metadata": dict(job_runtime.job.metadata or {}),
                    }
                    for job_runtime in runtime.jobs
                ],
            }
            for runtime in context.stages
        ],
    }


class TaskRuntimeExecutor:
    def __init__(
        self,
        project_root: Path,
        refresh_seconds: float = 1.0,
        logs_root: Path | None = None,
        job_start_timeout_sec: int | None = None,
        job_stall_timeout_sec: int | None = None,
        terminate_grace_sec: int | None = None,
    ) -> None:
        self.project_root = project_root
        self.refresh_seconds = refresh_seconds
        self.job_start_timeout_sec = int(job_start_timeout_sec or WATCHDOG_DEFAULTS["job_start_timeout_sec"])
        self.job_stall_timeout_sec = int(job_stall_timeout_sec or WATCHDOG_DEFAULTS["job_stall_timeout_sec"])
        self.terminate_grace_sec = int(terminate_grace_sec or WATCHDOG_DEFAULTS["terminate_grace_sec"])
        self.logs_root = logs_root or (project_root / "logs" / "task_runs")
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def execute(
        self,
        task: TaskSpec,
        *,
        normalized_params: dict[str, Any] | None = None,
        preset_id: str | None = None,
        run_id: str | None = None,
        stop_event: threading.Event | None = None,
        event_handler: RuntimeEventHandler | None = None,
        setup_hook: Callable[
            [
                TaskRunContext,
                RuntimeEventHandler | None,
                Callable[[str, str], None],
                Callable[[], None],
            ],
            None,
        ]
        | None = None,
    ) -> TaskRunContext:
        stop_event = stop_event or threading.Event()
        run_id = run_id or generate_run_id(task.slug)
        run_dir = self.logs_root / f"{time.strftime('%Y%m%d_%H%M%S')}_{task.slug}_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_stream_path = run_dir / "stream.jsonl"
        context = TaskRunContext(
            run_id=run_id,
            task=task,
            run_dir=run_dir,
            log_stream_path=log_stream_path,
            normalized_params=normalized_params or {},
            preset_id=preset_id,
            status="preflight" if setup_hook else "running",
            warnings=deepcopy(task.metadata.get("warnings") or []),
            stages=[
                StageRuntime(
                    stage=stage,
                    jobs=[
                        JobRuntime(
                            job=job,
                            log_path=run_dir / f"{stage.key}__{job.key}.log",
                        )
                        for job in stage.jobs
                    ],
                )
                for stage in task.stages
            ],
        )
        context.lifecycle["preflight_steps"] = deepcopy(
            task.metadata.get("effective_plan", {}).get("preflight_steps") or []
        )
        self._set_lifecycle(
            context,
            phase="preflight" if setup_hook else "running",
            label="BrowserMint preflight" if setup_hook else "Task running",
            detail="Preparing remote browser session and validating login state."
            if setup_hook
            else "Task is executing.",
        )
        self._emit_run_updated(context, event_handler)

        try:
            if setup_hook:
                try:
                    setup_hook(
                        context,
                        event_handler,
                        lambda message, level="info": self._append_system_log(
                            context,
                            message,
                            level,
                            event_handler,
                        ),
                        lambda: self._emit_run_updated(context, event_handler),
                    )
                except RunSetupError as exc:
                    self._set_lifecycle(
                        context,
                        phase=exc.status,
                        label="Waiting For User" if exc.status == "waiting_user" else "Preflight Failed",
                        detail=str(exc),
                    )
                    context.status = exc.status
                    context.finished_at = time.time()
                    self._append_system_log(context, str(exc), exc.level, event_handler)
                    self._emit_run_updated(context, event_handler)
                    return context
                except Exception as exc:
                    message = str(exc).strip() or exc.__class__.__name__
                    self._set_lifecycle(
                        context,
                        phase="failed",
                        label="Preflight Failed",
                        detail=message,
                    )
                    context.status = "failed"
                    context.finished_at = time.time()
                    self._append_system_log(context, message, "error", event_handler)
                    self._emit_run_updated(context, event_handler)
                    return context

            context.status = "running"
            for stage_runtime in context.stages:
                if stop_event.is_set():
                    context.interrupted = True
                    stage_runtime.status = "skipped"
                    continue

                stage_runtime.status = "running"
                self._set_lifecycle(
                    context,
                    phase="running",
                    label=stage_runtime.stage.name,
                    detail=f"Running stage {stage_runtime.stage.name}.",
                    current_stage_key=stage_runtime.stage.key,
                    current_stage_name=stage_runtime.stage.name,
                    stage_index=context.stages.index(stage_runtime) + 1,
                    stage_total=len(context.stages),
                )
                self._emit_run_updated(context, event_handler)
                self._run_stage(context, stage_runtime, stop_event, event_handler)
                if stop_event.is_set():
                    context.interrupted = True
                    break
                if stage_runtime.status == "failed" and stage_runtime.stage.abort_on_failure:
                    break

            if context.interrupted:
                for stage_runtime in context.stages:
                    if stage_runtime.status == "waiting":
                        stage_runtime.status = "skipped"
                        for job_runtime in stage_runtime.jobs:
                            job_runtime.status = "skipped"
                context.status = "stopped"
            else:
                failed_jobs = sum(
                    1
                    for stage_runtime in context.stages
                    for job_runtime in stage_runtime.jobs
                    if job_runtime.status == "failed"
                )
                degraded_jobs = sum(
                    1
                    for stage_runtime in context.stages
                    for job_runtime in stage_runtime.jobs
                    if job_runtime.status == "degraded"
                )
                if failed_jobs > 0:
                    context.status = "failed"
                elif degraded_jobs > 0:
                    context.status = "degraded"
                else:
                    context.status = "success"
            self._set_lifecycle(
                context,
                phase="finalizing",
                label="Finalizing",
                detail="Persisting final run state.",
                current_stage_key=None,
                current_stage_name=None,
                stage_index=len(context.stages),
                stage_total=len(context.stages),
            )
            context.finished_at = time.time()
            self._emit_run_updated(context, event_handler)
            return context
        except KeyboardInterrupt:
            context.interrupted = True
            context.status = "stopped"
            context.finished_at = time.time()
            self._terminate_running_jobs(context.stages)
            self._set_lifecycle(
                context,
                phase="stopped",
                label="Stopped",
                detail="Task execution was interrupted.",
                current_stage_key=None,
                current_stage_name=None,
            )
            self._emit_run_updated(context, event_handler)
            return context

    def _run_stage(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        stop_event: threading.Event,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        if stage_runtime.stage.concurrent:
            self._run_batch(
                context,
                stage_runtime,
                stage_runtime.jobs,
                stop_event,
                event_handler,
                max_parallel=stage_runtime.stage.max_parallel,
            )
            return

        for index, runtime in enumerate(stage_runtime.jobs):
            if stop_event.is_set():
                stage_runtime.status = "stopped"
                for pending in stage_runtime.jobs[index:]:
                    if pending.status == "waiting":
                        pending.status = "skipped"
                self._emit_run_updated(context, event_handler)
                return
            self._run_batch(context, stage_runtime, [runtime], stop_event, event_handler)
            if runtime.status == "failed" and stage_runtime.stage.abort_on_failure:
                stage_runtime.status = "failed"
                for pending in stage_runtime.jobs[index + 1 :]:
                    if pending.status == "waiting":
                        pending.status = "skipped"
                self._emit_run_updated(context, event_handler)
                return
        if not stop_event.is_set():
            if any(job_runtime.status == "failed" for job_runtime in stage_runtime.jobs):
                stage_runtime.status = "failed"
            elif any(job_runtime.status == "degraded" for job_runtime in stage_runtime.jobs):
                stage_runtime.status = "degraded"
            else:
                stage_runtime.status = "success"
            self._emit_run_updated(context, event_handler)

    def _run_batch(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtimes: list[JobRuntime],
        stop_event: threading.Event,
        event_handler: RuntimeEventHandler | None,
        max_parallel: int | None = None,
    ) -> None:
        if not runtimes:
            stage_runtime.status = "success"
            self._emit_run_updated(context, event_handler)
            return

        parallel_limit = max_parallel or len(runtimes)
        parallel_limit = max(1, min(parallel_limit, len(runtimes)))
        pending: deque[JobRuntime] = deque(runtimes)
        active: list[JobRuntime] = []
        has_failure = False

        def start_available_jobs() -> None:
            if stop_event.is_set():
                return
            while pending and len(active) < parallel_limit:
                runtime = pending.popleft()
                self._start_job(context, stage_runtime, runtime, event_handler)
                active.append(runtime)

        start_available_jobs()
        try:
            while active or pending:
                completed: list[JobRuntime] = []
                for runtime in list(active):
                    if runtime.status != "running" or not runtime.process:
                        completed.append(runtime)
                        continue

                    if stop_event.is_set():
                        break

                    self._tick_watchdog(context, stage_runtime, runtime, event_handler)
                    code = runtime.process.poll()
                    if code is None:
                        continue

                    if runtime.reader_thread:
                        runtime.reader_thread.join(timeout=2)
                    self._finalize_job_exit(
                        context,
                        stage_runtime,
                        runtime,
                        code,
                        event_handler,
                    )
                    if runtime.status == "failed":
                        has_failure = True
                    completed.append(runtime)

                for runtime in completed:
                    if runtime in active:
                        active.remove(runtime)
                    self._close_runtime_handles(runtime)

                if stop_event.is_set():
                    self._terminate_running_jobs([stage_runtime])
                    stage_runtime.status = "stopped"
                    for pending_runtime in pending:
                        if pending_runtime.status == "waiting":
                            pending_runtime.status = "skipped"
                    pending.clear()
                    self._emit_run_updated(context, event_handler)
                    break

                if has_failure and stage_runtime.stage.abort_on_failure:
                    for pending_runtime in pending:
                        if pending_runtime.status == "waiting":
                            pending_runtime.status = "skipped"
                    pending.clear()

                start_available_jobs()
                if not active and not pending:
                    break
                self._emit_run_updated(context, event_handler)
                time.sleep(self.refresh_seconds)
        finally:
            for runtime in active:
                self._close_runtime_handles(runtime)

        if stage_runtime.status != "stopped":
            if any(runtime.status == "failed" for runtime in stage_runtime.jobs):
                stage_runtime.status = "failed"
            elif any(runtime.status == "degraded" for runtime in stage_runtime.jobs):
                stage_runtime.status = "degraded"
            elif stage_runtime.stage.concurrent:
                stage_runtime.status = "success"
            else:
                stage_runtime.status = "running"
        self._emit_run_updated(context, event_handler)

    @staticmethod
    def _close_runtime_handles(runtime: JobRuntime) -> None:
        if runtime.reader_thread:
            runtime.reader_thread.join(timeout=2)
            runtime.reader_thread = None
        if runtime.log_fp:
            runtime.log_fp.close()
            runtime.log_fp = None

    def _start_job(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtime: JobRuntime,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        runtime.status = "running"
        runtime.started_at = time.time()
        runtime.last_state_change_at = runtime.started_at
        runtime.watchdog_status = "starting"
        runtime.stall_deadline_at = runtime.started_at + self.job_start_timeout_sec
        runtime.log_path.parent.mkdir(parents=True, exist_ok=True)
        runtime.log_fp = runtime.log_path.open("w", encoding="utf-8", newline="")

        job_env = {
            **os.environ,
            **runtime.job.env,
            "SOCIAL_CRAWLER_RUN_ID": context.run_id,
            "SOCIAL_CRAWLER_TASK_SLUG": context.task.slug,
            "SOCIAL_CRAWLER_STAGE_KEY": stage_runtime.stage.key,
            "SOCIAL_CRAWLER_JOB_KEY": runtime.job.key,
        }
        process = subprocess.Popen(
            runtime.job.command,
            cwd=str(runtime.job.cwd),
            env=job_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )

        runtime.process = process
        runtime.reader_thread = threading.Thread(
            target=self._consume_output,
            args=(context, stage_runtime, runtime, event_handler),
            daemon=True,
        )
        runtime.reader_thread.start()
        self._emit_run_updated(context, event_handler)

    def _consume_output(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtime: JobRuntime,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        assert runtime.process is not None
        assert runtime.log_fp is not None

        stream = runtime.process.stdout
        if stream is None:
            return

        for raw_line in stream:
            runtime.log_fp.write(raw_line)
            runtime.log_fp.flush()
            with self._lock:
                runtime.line_count += 1
                runtime.last_output_at = time.time()
                runtime.watchdog_status = "healthy"
                runtime.stall_deadline_at = runtime.last_output_at + self.job_stall_timeout_sec
                cleaned = raw_line.rstrip().replace("\r", "")
                if cleaned:
                    runtime.last_line = cleaned[-120:]
                    self._append_log_entry(
                        context,
                        stage_runtime=stage_runtime,
                        runtime=runtime,
                        message=cleaned,
                        level=self._parse_log_level(cleaned),
                        event_handler=event_handler,
                    )

    def _append_log_entry(
        self,
        context: TaskRunContext,
        *,
        stage_runtime: StageRuntime,
        runtime: JobRuntime,
        message: str,
        level: str,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        entry = {
            "id": context.next_log_id,
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "stage_key": stage_runtime.stage.key,
            "stage_name": stage_runtime.stage.name,
            "job_key": runtime.job.key,
            "job_name": runtime.job.name,
        }
        context.next_log_id += 1
        context.log_entries.append(entry)
        self._record_runtime_metrics(context, runtime, message)
        self._record_issue_summary(context, entry)
        with context.log_stream_path.open("a", encoding="utf-8") as log_stream:
            log_stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if event_handler:
            event_handler({"type": "log", "run_id": context.run_id, "entry": entry})

    def _emit_run_updated(
        self,
        context: TaskRunContext,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        if event_handler:
            event_handler({"type": "run_updated", "run": serialize_run_context(context)})

    def _append_system_log(
        self,
        context: TaskRunContext,
        message: str,
        level: str,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        self._append_log_entry(
            context,
            stage_runtime=StageRuntime(
                stage=TaskStage(key=_SYSTEM_STAGE_KEY, name=_SYSTEM_STAGE_NAME, jobs=[]),
                jobs=[],
            ),
            runtime=JobRuntime(
                job=TaskJob(key=_SYSTEM_JOB_KEY, name=_SYSTEM_JOB_NAME, command=[], cwd=context.run_dir),
                log_path=context.run_dir / "preflight.log",
            ),
            message=message,
            level=level,
            event_handler=event_handler,
        )

    @staticmethod
    def _set_lifecycle(
        context: TaskRunContext,
        *,
        phase: str,
        label: str,
        detail: str,
        current_stage_key: str | None = None,
        current_stage_name: str | None = None,
        stage_index: int | None = None,
        stage_total: int | None = None,
    ) -> None:
        context.lifecycle.update(
            {
                "phase": phase,
                "label": label,
                "detail": detail,
                "updated_at": datetime.now().isoformat(),
                "current_stage_key": current_stage_key,
                "current_stage_name": current_stage_name,
                "stage_index": stage_index if stage_index is not None else context.lifecycle.get("stage_index", 0),
                "stage_total": stage_total if stage_total is not None else context.lifecycle.get("stage_total", 0),
            }
        )

    def _finalize_job_exit(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtime: JobRuntime,
        code: int,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        runtime.exit_code = code
        runtime.finished_at = time.time()
        runtime.last_state_change_at = runtime.finished_at
        if runtime.termination_reason:
            runtime.status = "failed"
            runtime.watchdog_status = "terminated"
            return

        if code != 0:
            runtime.status = "failed"
            runtime.watchdog_status = "completed"
            runtime.termination_reason = self._summarize_failure_reason(runtime)
            self._append_log_entry(
                context,
                stage_runtime=stage_runtime,
                runtime=runtime,
                message=(
                    f"[runner] Job exited with code {code}. "
                    f"Reason: {runtime.termination_reason}"
                ),
                level="error",
                event_handler=event_handler,
            )
            return

        degradation_reason = self._detect_degraded_job(runtime)
        if degradation_reason:
            runtime.status = "degraded"
            runtime.watchdog_status = "completed"
            runtime.termination_reason = degradation_reason
            _append_warning(
                context,
                {
                    "code": "detail_failure_ratio_high",
                    "level": "warning",
                    "message": degradation_reason,
                    "stage_key": stage_runtime.stage.key,
                    "job_key": runtime.job.key,
                    "issue_group": "detail_failure_ratio_high",
                },
            )
            self._append_log_entry(
                context,
                stage_runtime=stage_runtime,
                runtime=runtime,
                message=f"[issue:detail_failure_ratio_high] {degradation_reason}",
                level="warning",
                event_handler=event_handler,
            )
            return

        runtime.status = "success"
        runtime.watchdog_status = "completed"

    @staticmethod
    def _detect_degraded_job(runtime: JobRuntime) -> str | None:
        detail_requests = int(runtime.runtime_metrics.get("detail_requests", 0))
        detail_successes = int(runtime.runtime_metrics.get("detail_successes", 0))
        detail_failures = int(runtime.runtime_metrics.get("detail_failures", 0))
        if detail_requests > 0 and detail_successes == 0:
            return f"Detail fetch degraded: 0/{detail_requests} succeeded."
        if detail_requests >= 10 and detail_failures > 0:
            failure_ratio = detail_failures / max(1, detail_requests)
            if failure_ratio >= 0.8:
                return (
                    "Detail fetch degraded: "
                    f"{detail_successes}/{detail_requests} succeeded "
                    f"({detail_failures} failed)."
                )
        return None

    @staticmethod
    def _record_runtime_metrics(
        context: TaskRunContext,
        runtime: JobRuntime,
        message: str,
    ) -> None:
        note_count = message.count("'model_type': 'note'")
        if note_count:
            context.runtime_metrics["candidate_count"] += note_count

        detail_match = _NOTE_DETAILS_RE.search(message)
        if not detail_match:
            return
        try:
            details = ast.literal_eval(detail_match.group(1))
        except (ValueError, SyntaxError):
            return
        if not isinstance(details, list):
            return
        context.runtime_metrics["detail_requests"] += len(details)
        runtime.runtime_metrics["detail_requests"] += len(details)
        success_count = sum(1 for item in details if item is not None)
        context.runtime_metrics["detail_successes"] += success_count
        runtime.runtime_metrics["detail_successes"] += success_count
        context.runtime_metrics["detail_failures"] += len(details) - success_count
        runtime.runtime_metrics["detail_failures"] += len(details) - success_count

    @staticmethod
    def _record_issue_summary(context: TaskRunContext, entry: dict[str, Any]) -> None:
        level = str(entry.get("level") or "").lower()
        if level not in {"warning", "warn", "error"}:
            return
        message = str(entry.get("message") or "")
        category_key, label, hint = _classify_issue(message)
        fingerprint = f"{category_key}:{_normalize_issue_fingerprint(message)}"
        summary = context.issue_summaries.get(fingerprint)
        if summary is None:
            summary = {
                "fingerprint": fingerprint,
                "category_key": category_key,
                "label": label,
                "hint": hint,
                "count": 0,
                "level": level,
                "sample_message": message,
                "first_seen_at": entry.get("timestamp"),
                "last_seen_at": entry.get("timestamp"),
                "stage_key": entry.get("stage_key"),
                "stage_name": entry.get("stage_name"),
                "job_key": entry.get("job_key"),
                "job_name": entry.get("job_name"),
                "affected_slices": [],
            }
            context.issue_summaries[fingerprint] = summary
        summary["count"] = int(summary.get("count", 0)) + 1
        summary["last_seen_at"] = entry.get("timestamp")
        summary["last_message"] = message
        affected_slices = summary.setdefault("affected_slices", [])
        slice_ref = {
            "stage_key": entry.get("stage_key"),
            "stage_name": entry.get("stage_name"),
            "job_key": entry.get("job_key"),
            "job_name": entry.get("job_name"),
        }
        if slice_ref not in affected_slices:
            affected_slices.append(slice_ref)
            del affected_slices[10:]

    def _tick_watchdog(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtime: JobRuntime,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        if runtime.status != "running" or runtime.process is None:
            return

        now = time.time()
        if runtime.termination_requested_at:
            if now - runtime.termination_requested_at >= self.terminate_grace_sec:
                self._signal_process(runtime, sig=signal.SIGKILL)
            return

        deadline = runtime.stall_deadline_at
        if deadline is None or now < deadline:
            return

        if runtime.last_output_at is None:
            runtime.termination_reason = (
                f"No job output within {self.job_start_timeout_sec}s start timeout."
            )
            runtime.watchdog_status = "stalled"
        else:
            runtime.termination_reason = (
                f"No job output within {self.job_stall_timeout_sec}s stall timeout."
            )
            runtime.watchdog_status = "stalled"
        runtime.watchdog_triggered = True
        runtime.last_state_change_at = now
        runtime.termination_requested_at = now
        runtime.stall_deadline_at = now + self.terminate_grace_sec
        self._append_log_entry(
            context,
            stage_runtime=stage_runtime,
            runtime=runtime,
            message=f"[watchdog] {runtime.termination_reason} Sending terminate signal.",
            level="warning",
            event_handler=event_handler,
        )
        self._signal_process(runtime, sig=signal.SIGTERM)

    def _terminate_running_jobs(self, stage_runtimes: list[StageRuntime]) -> None:
        jobs = [job for stage in stage_runtimes for job in stage.jobs]
        for runtime in jobs:
            process = runtime.process
            if runtime.status != "running" or process is None:
                continue
            runtime.termination_reason = runtime.termination_reason or "Stopped by user."
            runtime.watchdog_status = "terminating"
            runtime.termination_requested_at = time.time()
            runtime.last_state_change_at = runtime.termination_requested_at
            self._signal_process(runtime, sig=signal.SIGTERM)

        deadline = time.time() + 5
        while time.time() < deadline:
            alive = [
                runtime.process
                for runtime in jobs
                if runtime.status == "running" and runtime.process and runtime.process.poll() is None
            ]
            if not alive:
                break
            time.sleep(0.2)

        for runtime in jobs:
            process = runtime.process
            if runtime.status != "running" or process is None:
                continue
            if process.poll() is None:
                self._signal_process(runtime, sig=signal.SIGKILL)
            runtime.status = "stopped"
            runtime.exit_code = -1
            runtime.finished_at = time.time()
            runtime.last_state_change_at = runtime.finished_at
            runtime.watchdog_status = "stopped"

    def _signal_process(self, runtime: JobRuntime, *, sig: int) -> None:
        process = runtime.process
        if process is None:
            return
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(process.pid), sig)
                return
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        except ProcessLookupError:
            return
        except Exception:
            if sig == signal.SIGTERM:
                try:
                    process.terminate()
                except Exception:
                    return
            else:
                try:
                    process.kill()
                except Exception:
                    return

    @staticmethod
    def _parse_log_level(line: str) -> str:
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAILED" in line_upper:
            return "error"
        if "WARNING" in line_upper or "WARN" in line_upper:
            return "warning"
        if "SUCCESS" in line_upper or "完成" in line or "成功" in line:
            return "success"
        if "DEBUG" in line_upper:
            return "debug"
        return "info"

    def _summarize_failure_reason(self, runtime: JobRuntime) -> str:
        """Extract a short, user-facing failure reason from recent logs."""
        tail_lines: deque[str] = deque(maxlen=120)
        try:
            with runtime.log_path.open("r", encoding="utf-8", errors="replace") as fp:
                for line in fp:
                    cleaned = line.strip()
                    if cleaned:
                        tail_lines.append(cleaned)
        except Exception:
            pass

        readable_patterns = (
            (
                "Missing X server or $DISPLAY",
                "缺少图形显示环境（DISPLAY），二维码登录无法弹出浏览器。",
            ),
            (
                "The platform failed to initialize",
                "浏览器图形环境初始化失败，请确认 DISPLAY 或改用 Cookie 登录。",
            ),
            (
                "DataFetchError: 您当前登录的账号没有权限访问",
                "当前登录账号没有权限访问目标内容。",
            ),
            (
                "DataFetchError",
                "数据拉取失败，请检查账号权限或平台风控状态。",
            ),
        )
        for line in reversed(tail_lines):
            for pattern, reason in readable_patterns:
                if pattern in line:
                    return reason

        priority_tokens = (
            "DataFetchError",
            "RetryError",
            "Error:",
            "Exception:",
            "HTTPError",
            "没有权限",
            "not found",
            "timed out",
        )
        skip_prefixes = (
            "Traceback",
            "File \"",
            "raise ",
            "return ",
            "^",
        )

        for line in reversed(tail_lines):
            if line.startswith(skip_prefixes):
                continue
            if any(token in line for token in priority_tokens):
                return line[:280]

        if runtime.last_line:
            return runtime.last_line[:280]

        for line in reversed(tail_lines):
            if not line.startswith(skip_prefixes):
                return line[:280]

        exit_code = runtime.exit_code if runtime.exit_code is not None else "unknown"
        return f"Process exited with code {exit_code}."
