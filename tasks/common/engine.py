from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from tasks.common.models import TaskSpec
from tasks.common.runtime import TaskRunContext, TaskRuntimeExecutor
from tools import runtime_paths


class TaskExecutionEngine:
    def __init__(self, project_root: Path, refresh_seconds: float = 1.5) -> None:
        self.project_root = project_root
        self.refresh_seconds = refresh_seconds
        runtime_paths.ensure_runtime_layout()
        self.logs_root = runtime_paths.get_task_runs_dir()
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self._dynamic_screen = bool(sys.stdout.isatty())
        self._latest_snapshot: dict | None = None

    def run_task(self, task: TaskSpec) -> int:
        self._welcome_printed = False
        executor = TaskRuntimeExecutor(
            project_root=self.project_root,
            refresh_seconds=self.refresh_seconds,
            logs_root=self.logs_root,
        )
        context = executor.execute(task, event_handler=self._handle_event)
        return self._print_final_summary(context)

    def _handle_event(self, event: dict) -> None:
        if event.get("type") != "run_updated":
            return
        self._latest_snapshot = event["run"]
        if not self._latest_snapshot:
            return
        if self._latest_snapshot["started_at"] and not getattr(self, "_welcome_printed", False):
            self._print_task_welcome_from_snapshot(self._latest_snapshot)
            self._welcome_printed = True
        self._render_live(self._latest_snapshot)

    def _print_task_welcome(self, task: TaskSpec, run_dir: Path) -> None:
        print("=" * 96)
        print(f"[Task] {task.title} ({task.slug})")
        print("=" * 96)
        print(f"[Logs] {run_dir}")
        print("[Capabilities]")
        for item in task.capabilities:
            print(f"  - {item}")
        print("[Task Welcome]")
        for line in task.welcome_lines:
            print(f"  {line}")
        print()

    def _print_task_welcome_from_snapshot(self, snapshot: dict) -> None:
        task = snapshot
        print("=" * 96)
        print(f"[Task] {task['title']} ({task['task_slug']})")
        print("=" * 96)
        if task.get("log_path"):
            print(f"[Logs] {Path(task['log_path']).parent}")
        print()

    def _render_live(self, snapshot: dict) -> None:
        if self._dynamic_screen:
            print("\x1b[2J\x1b[H", end="")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 96)
        print(f"[Progress] {snapshot['title']}  |  {now}  |  status={snapshot['status']}")
        print("=" * 96)
        print(f"{'Stage / Job':34} {'Status':10} {'Duration':9} {'Lines':7} Last Output")
        print("-" * 96)

        for stage in snapshot["stages"]:
            stage_label = stage["name"][:34]
            print(f"{stage_label:34} {stage['status'].upper():10} {'-':9} {'-':7} -")
            for job in stage["jobs"]:
                duration = self._format_duration(job["started_at"], job["finished_at"])
                last_line = job["last_line"] or "-"
                job_label = f"  {job['name']}"[:34]
                print(
                    f"{job_label:34} {job['status'].upper():10} {duration:9} "
                    f"{job['line_count']:7d} {last_line}"
                )

        print("-" * 96)
        print("[Stage Result] running... (Ctrl+C to stop current task)")

    def _print_final_summary(self, context: TaskRunContext) -> int:
        results = [job for stage in context.stages for job in stage.jobs]
        total = len(results)
        success = sum(1 for job in results if job.status == "success")
        failed = total - success

        print("\n" + "=" * 96)
        print(f"[Final Summary] {context.task.title}")
        print("=" * 96)
        print(f"Total jobs : {total}")
        print(f"Success    : {success}")
        print(f"Failed     : {failed}")
        print(f"Logs path  : {context.run_dir}")
        print("-" * 96)

        if total > 0:
            print(f"{'Job':26} {'Status':10} {'Duration':9} {'Exit':6} Log File")
            print("-" * 96)
            for runtime in results:
                duration = self._format_duration(
                    (
                        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(runtime.started_at))
                        if runtime.started_at
                        else None
                    ),
                    (
                        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(runtime.finished_at))
                        if runtime.finished_at
                        else None
                    ),
                )
                code_text = "-" if runtime.exit_code is None else str(runtime.exit_code)
                print(
                    f"{runtime.job.name[:26]:26} {runtime.status.upper():10} {duration:9} "
                    f"{code_text:6} {runtime.log_path}"
                )

        print("=" * 96)

        if context.interrupted:
            print("[Exit] Interrupted by user.")
            return 130
        if total == 0:
            print("[Exit] No job executed.")
            return 1
        return 0 if failed == 0 else 1

    @staticmethod
    def _format_duration(started_at: str | None, finished_at: str | None) -> str:
        if not started_at:
            return "-"
        start = datetime.fromisoformat(started_at).timestamp()
        end = datetime.fromisoformat(finished_at).timestamp() if finished_at else time.time()
        sec = max(0, int(end - start))
        mm, ss = divmod(sec, 60)
        return f"{mm:02d}:{ss:02d}"
