from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any

from tasks.common.models import TaskSpec
from tasks.common.runtime import TaskRuntimeExecutor, generate_run_id

from .task_center_store import TaskCenterFileStore


def _build_initial_snapshot(
    *,
    run_id: str,
    task: TaskSpec,
    normalized_params: dict[str, Any],
    preset_id: str | None,
) -> dict[str, Any]:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    return {
        "id": run_id,
        "task_slug": task.slug,
        "title": task.title,
        "status": "running",
        "preset_id": preset_id,
        "normalized_params": normalized_params,
        "started_at": started_at,
        "finished_at": None,
        "log_path": "",
        "metrics": {
            "accepted": 0,
            "filtered": 0,
            "deduped": 0,
            "errors": 0,
            "stalled_jobs": 0,
        },
        "stages": [
            {
                "key": stage.key,
                "name": stage.name,
                "concurrent": stage.concurrent,
                "max_parallel": stage.max_parallel,
                "abort_on_failure": stage.abort_on_failure,
                "status": "waiting",
                "jobs": [
                    {
                        "key": job.key,
                        "name": job.name,
                        "status": "waiting",
                        "cwd": str(job.cwd),
                        "command": list(job.command),
                        "log_path": "",
                        "exit_code": None,
                        "line_count": 0,
                        "last_line": "",
                        "pid": None,
                        "last_output_at": None,
                        "last_state_change_at": None,
                        "watchdog_status": "idle",
                        "stall_deadline_at": None,
                        "termination_reason": None,
                        "started_at": None,
                        "finished_at": None,
                    }
                    for job in stage.jobs
                ],
            }
            for stage in task.stages
        ],
    }


class TaskRunManager:
    def __init__(self, project_root: Path, store: TaskCenterFileStore) -> None:
        self.project_root = project_root
        self.store = store
        self.executor = TaskRuntimeExecutor(project_root=project_root)
        self._lock = threading.Lock()
        self._active_run_id: str | None = None
        self._active_snapshot: dict[str, Any] | None = None
        self._active_stop_event: threading.Event | None = None
        self._active_thread: threading.Thread | None = None
        self._run_logs: dict[str, list[dict[str, Any]]] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=4000)
        self._next_event_id = 1

    def start_run(
        self,
        task: TaskSpec,
        *,
        normalized_params: dict[str, Any],
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._active_thread and self._active_thread.is_alive():
                raise RuntimeError("Another task is already running.")

            run_id = generate_run_id(task.slug)
            snapshot = _build_initial_snapshot(
                run_id=run_id,
                task=task,
                normalized_params=normalized_params,
                preset_id=preset_id,
            )
            stop_event = threading.Event()
            self._active_run_id = run_id
            self._active_snapshot = snapshot
            self._active_stop_event = stop_event
            self._run_logs[run_id] = []
            self.store.upsert_run(snapshot)
            self._record_event({"type": "run_updated", "run": deepcopy(snapshot)})

            thread = threading.Thread(
                target=self._run_worker,
                args=(run_id, task, normalized_params, preset_id, stop_event),
                daemon=True,
            )
            self._active_thread = thread
            thread.start()
            return deepcopy(snapshot)

    def stop_active_run(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._active_run_id or not self._active_stop_event:
                return None
            self._active_stop_event.set()
            return deepcopy(self._active_snapshot) if self._active_snapshot else None

    def get_active_run(self) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(self._active_snapshot) if self._active_snapshot else None

    def list_runs(self) -> list[dict[str, Any]]:
        return self.store.load_runs()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        active = self.get_active_run()
        if active and active.get("id") == run_id:
            return active
        return self.store.get_run(run_id)

    def get_run_logs(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if run_id in self._run_logs:
                return deepcopy(self._run_logs[run_id][-limit:])

        run = self.get_run(run_id)
        if not run or not run.get("log_path"):
            return []

        log_path = Path(run["log_path"])
        if not log_path.exists():
            return []

        logs: deque[dict[str, Any]] = deque(maxlen=limit)
        with log_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return list(logs)

    def get_recent_active_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if not self._active_run_id:
                return []
            return deepcopy(self._run_logs.get(self._active_run_id, [])[-limit:])

    def get_events_since(self, event_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(event) for event in self._events if event["event_id"] > event_id]

    def _run_worker(
        self,
        run_id: str,
        task: TaskSpec,
        normalized_params: dict[str, Any],
        preset_id: str | None,
        stop_event: threading.Event,
    ) -> None:
        try:
            self.executor.execute(
                task,
                normalized_params=normalized_params,
                preset_id=preset_id,
                run_id=run_id,
                stop_event=stop_event,
                event_handler=self._handle_runtime_event,
            )
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None
                    self._active_snapshot = None
                    self._active_stop_event = None
                    self._active_thread = None

    def _handle_runtime_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "run_updated":
            snapshot = deepcopy(event["run"])
            with self._lock:
                self.store.upsert_run(snapshot)
                if snapshot.get("id") == self._active_run_id:
                    self._active_snapshot = snapshot
                self._record_event({"type": "run_updated", "run": snapshot})
            return

        if event_type == "log":
            run_id = str(event["run_id"])
            entry = deepcopy(event["entry"])
            with self._lock:
                logs = self._run_logs.setdefault(run_id, [])
                logs.append(entry)
                if len(logs) > 4000:
                    del logs[:-2000]
                self._record_event({"type": "log", "run_id": run_id, "entry": entry})

    def _record_event(self, payload: dict[str, Any]) -> None:
        event = {"event_id": self._next_event_id, **payload}
        self._next_event_id += 1
        self._events.append(event)
