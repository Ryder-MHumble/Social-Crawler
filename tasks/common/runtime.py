from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from database.sqlite_storage import WATCHDOG_DEFAULTS, get_sqlite_storage
from tasks.common.models import TaskJob, TaskSpec, TaskStage

RuntimeEventHandler = Callable[[dict[str, Any]], None]


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


def generate_run_id(prefix: str = "run") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def serialize_run_context(context: TaskRunContext) -> dict[str, Any]:
    sqlite_metrics = get_sqlite_storage().get_run_metrics(context.run_id)
    stalled_jobs = sum(
        1
        for stage_runtime in context.stages
        for job_runtime in stage_runtime.jobs
        if job_runtime.termination_reason
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
            "stalled_jobs": stalled_jobs,
        },
        "stages": [
            {
                "key": runtime.stage.key,
                "name": runtime.stage.name,
                "concurrent": runtime.stage.concurrent,
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
        self._emit_run_updated(context, event_handler)

        try:
            for stage_runtime in context.stages:
                if stop_event.is_set():
                    context.interrupted = True
                    stage_runtime.status = "skipped"
                    continue

                stage_runtime.status = "running"
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
                context.status = "success" if failed_jobs == 0 else "failed"
            context.finished_at = time.time()
            self._emit_run_updated(context, event_handler)
            return context
        except KeyboardInterrupt:
            context.interrupted = True
            context.status = "stopped"
            context.finished_at = time.time()
            self._terminate_running_jobs(context.stages)
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
            self._run_batch(context, stage_runtime, stage_runtime.jobs, stop_event, event_handler)
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
            stage_runtime.status = (
                "failed"
                if any(job_runtime.status == "failed" for job_runtime in stage_runtime.jobs)
                else "success"
            )
            self._emit_run_updated(context, event_handler)

    def _run_batch(
        self,
        context: TaskRunContext,
        stage_runtime: StageRuntime,
        runtimes: list[JobRuntime],
        stop_event: threading.Event,
        event_handler: RuntimeEventHandler | None,
    ) -> None:
        if not runtimes:
            stage_runtime.status = "success"
            self._emit_run_updated(context, event_handler)
            return

        for runtime in runtimes:
            self._start_job(context, stage_runtime, runtime, event_handler)

        try:
            while True:
                running_count = 0
                for runtime in runtimes:
                    if runtime.status != "running" or not runtime.process:
                        continue

                    if stop_event.is_set():
                        break

                    self._tick_watchdog(context, stage_runtime, runtime, event_handler)
                    code = runtime.process.poll()
                    if code is None:
                        running_count += 1
                        continue

                    runtime.exit_code = code
                    runtime.finished_at = time.time()
                    runtime.last_state_change_at = runtime.finished_at
                    if runtime.termination_reason:
                        runtime.status = "failed"
                        runtime.watchdog_status = "terminated"
                    else:
                        runtime.status = "success" if code == 0 else "failed"
                        runtime.watchdog_status = "completed"
                        if code != 0:
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

                if stop_event.is_set():
                    self._terminate_running_jobs([stage_runtime])
                    stage_runtime.status = "stopped"
                    self._emit_run_updated(context, event_handler)
                    break

                if running_count == 0:
                    break
                self._emit_run_updated(context, event_handler)
                time.sleep(self.refresh_seconds)
        finally:
            for runtime in runtimes:
                if runtime.reader_thread:
                    runtime.reader_thread.join(timeout=2)
                if runtime.log_fp:
                    runtime.log_fp.close()
                    runtime.log_fp = None

        if stage_runtime.status != "stopped":
            stage_runtime.status = (
                "failed"
                if stage_runtime.stage.concurrent
                and any(runtime.status == "failed" for runtime in stage_runtime.jobs)
                else ("success" if stage_runtime.stage.concurrent else "running")
            )
        self._emit_run_updated(context, event_handler)

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
