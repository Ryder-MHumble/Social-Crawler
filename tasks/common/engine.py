from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tasks.common.models import TaskJob, TaskSpec, TaskStage


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
    process: Optional[subprocess.Popen] = None
    reader_thread: Optional[threading.Thread] = None
    log_fp: Optional[object] = None


class TaskExecutionEngine:
    def __init__(self, project_root: Path, refresh_seconds: float = 1.5) -> None:
        self.project_root = project_root
        self.refresh_seconds = refresh_seconds
        self.logs_root = project_root / "logs" / "task_runs"
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._dynamic_screen = bool(sys.stdout.isatty())

    def run_task(self, task: TaskSpec) -> int:
        run_tag = f"{time.strftime('%Y%m%d_%H%M%S')}_{task.slug}"
        run_dir = self.logs_root / run_tag
        run_dir.mkdir(parents=True, exist_ok=True)

        self._print_task_welcome(task, run_dir)

        all_results: list[JobRuntime] = []
        interrupted = False

        for idx, stage in enumerate(task.stages, start=1):
            self._print_stage_header(idx, len(task.stages), stage)
            try:
                stage_results = self._run_stage(stage, run_dir)
            except KeyboardInterrupt:
                interrupted = True
                break

            all_results.extend(stage_results)
            stage_failed = any(item.status != "success" for item in stage_results)
            if stage_failed and stage.abort_on_failure:
                print(
                    f"\n[Stage Halt] '{stage.name}' has failures. "
                    "Stopping remaining stages because abort_on_failure=True."
                )
                break

        return self._print_final_summary(task, all_results, run_dir, interrupted=interrupted)

    def _run_stage(self, stage: TaskStage, run_dir: Path) -> list[JobRuntime]:
        runtimes = [
            JobRuntime(
                job=job,
                log_path=run_dir / f"{stage.key}__{job.key}.log",
            )
            for job in stage.jobs
        ]

        if stage.concurrent:
            return self._run_batch(stage.name, runtimes)

        finished: list[JobRuntime] = []
        for runtime in runtimes:
            batch_result = self._run_batch(stage.name, [runtime])
            finished.extend(batch_result)
            if batch_result and batch_result[0].status != "success" and stage.abort_on_failure:
                break
        return finished

    def _run_batch(self, stage_name: str, runtimes: list[JobRuntime]) -> list[JobRuntime]:
        if not runtimes:
            return []

        for runtime in runtimes:
            self._start_job(runtime)

        try:
            while True:
                running_count = 0
                for runtime in runtimes:
                    if runtime.status != "running" or not runtime.process:
                        continue
                    code = runtime.process.poll()
                    if code is None:
                        running_count += 1
                        continue

                    runtime.exit_code = code
                    runtime.finished_at = time.time()
                    runtime.status = "success" if code == 0 else "failed"

                self._render_live(stage_name, runtimes)
                if running_count == 0:
                    break
                time.sleep(self.refresh_seconds)
        except KeyboardInterrupt:
            self._terminate_running_jobs(runtimes)
            raise
        finally:
            for runtime in runtimes:
                if runtime.reader_thread:
                    runtime.reader_thread.join(timeout=2)
                if runtime.log_fp:
                    runtime.log_fp.close()

        self._render_live(stage_name, runtimes, final=True)
        return runtimes

    def _start_job(self, runtime: JobRuntime) -> None:
        runtime.status = "running"
        runtime.started_at = time.time()
        runtime.log_path.parent.mkdir(parents=True, exist_ok=True)
        runtime.log_fp = runtime.log_path.open("w", encoding="utf-8", newline="")

        env = os.environ.copy()
        env.update(runtime.job.env)

        process = subprocess.Popen(
            runtime.job.command,
            cwd=str(runtime.job.cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        runtime.process = process
        runtime.reader_thread = threading.Thread(
            target=self._consume_output,
            args=(runtime,),
            daemon=True,
        )
        runtime.reader_thread.start()

    def _consume_output(self, runtime: JobRuntime) -> None:
        assert runtime.process is not None
        assert runtime.log_fp is not None

        stream = runtime.process.stdout
        if stream is None:
            return

        for raw_line in stream:
            runtime.log_fp.write(raw_line)
            with self._lock:
                runtime.line_count += 1
                cleaned = raw_line.rstrip().replace("\r", "")
                if cleaned:
                    runtime.last_line = cleaned[-90:]
            runtime.log_fp.flush()

    def _terminate_running_jobs(self, runtimes: list[JobRuntime]) -> None:
        for runtime in runtimes:
            process = runtime.process
            if runtime.status != "running" or process is None:
                continue
            process.terminate()

        deadline = time.time() + 5
        while time.time() < deadline:
            alive = [
                rt.process
                for rt in runtimes
                if rt.status == "running" and rt.process and rt.process.poll() is None
            ]
            if not alive:
                break
            time.sleep(0.2)

        for runtime in runtimes:
            process = runtime.process
            if runtime.status != "running" or process is None:
                continue
            if process.poll() is None:
                process.kill()
            runtime.status = "failed"
            runtime.exit_code = -1
            runtime.finished_at = time.time()

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

    def _print_stage_header(self, idx: int, total: int, stage: TaskStage) -> None:
        mode = "parallel" if stage.concurrent else "sequential"
        print("-" * 96)
        print(f"[Stage {idx}/{total}] {stage.name}  |  mode={mode}  |  jobs={len(stage.jobs)}")
        print("-" * 96)

    def _render_live(self, stage_name: str, runtimes: list[JobRuntime], final: bool = False) -> None:
        if self._dynamic_screen:
            print("\x1b[2J\x1b[H", end="")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 96)
        print(f"[Progress] {stage_name}  |  {now}")
        print("=" * 96)
        print(f"{'Job':26} {'Status':10} {'Duration':9} {'Lines':7} Last Output")
        print("-" * 96)

        for runtime in runtimes:
            duration = self._format_duration(runtime)
            status_text = runtime.status.upper()
            last_line = runtime.last_line or "-"
            print(
                f"{runtime.job.name[:26]:26} {status_text:10} {duration:9} "
                f"{runtime.line_count:7d} {last_line}"
            )

        if final:
            print("-" * 96)
            print("[Stage Result] completed")
        else:
            print("-" * 96)
            print("[Stage Result] running... (Ctrl+C to stop current task)")

    def _print_final_summary(
        self,
        task: TaskSpec,
        results: list[JobRuntime],
        run_dir: Path,
        interrupted: bool = False,
    ) -> int:
        total = len(results)
        success = sum(1 for item in results if item.status == "success")
        failed = total - success

        print("\n" + "=" * 96)
        print(f"[Final Summary] {task.title}")
        print("=" * 96)
        print(f"Total jobs : {total}")
        print(f"Success    : {success}")
        print(f"Failed     : {failed}")
        print(f"Logs path  : {run_dir}")
        print("-" * 96)

        if total > 0:
            print(f"{'Job':26} {'Status':10} {'Duration':9} {'Exit':6} Log File")
            print("-" * 96)
            for runtime in results:
                duration = self._format_duration(runtime)
                code_text = "-" if runtime.exit_code is None else str(runtime.exit_code)
                print(
                    f"{runtime.job.name[:26]:26} {runtime.status.upper():10} {duration:9} "
                    f"{code_text:6} {runtime.log_path}"
                )

        print("=" * 96)

        if interrupted:
            print("[Exit] Interrupted by user.")
            return 130
        if total == 0:
            print("[Exit] No job executed.")
            return 1
        return 0 if failed == 0 else 1

    @staticmethod
    def _format_duration(runtime: JobRuntime) -> str:
        if not runtime.started_at:
            return "-"
        end = runtime.finished_at or time.time()
        sec = max(0, int(end - runtime.started_at))
        mm, ss = divmod(sec, 60)
        return f"{mm:02d}:{ss:02d}"

