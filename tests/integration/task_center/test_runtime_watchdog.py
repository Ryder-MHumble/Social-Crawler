from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import pytest

from config.db_config import sqlite_db_config
from database import sqlite_storage as sqlite_storage_module
from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.runtime import TaskRuntimeExecutor

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_env(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "watchdog.sqlite3"
    monkeypatch.setitem(sqlite_db_config, "db_path", str(db_path))
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)
    yield sqlite_storage_module.get_sqlite_storage()
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)


def _task_for(command: list[str], workdir: Path) -> TaskSpec:
    return TaskSpec(
        slug="watchdog_dummy",
        title="Watchdog Dummy",
        short_desc="dummy",
        capabilities=["test"],
        welcome_lines=["watchdog"],
        stages=[
            TaskStage(
                key="dummy_stage",
                name="Dummy Stage",
                jobs=[
                    TaskJob(
                        key="dummy_job",
                        name="Dummy Job",
                        command=command,
                        cwd=workdir,
                    )
                ],
                concurrent=False,
                abort_on_failure=False,
            )
        ],
        aliases=[],
    )


def _run_task(tmp_path: Path, command: list[str]) -> tuple[object, object]:
    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=1,
        job_stall_timeout_sec=1,
        terminate_grace_sec=1,
    )
    context = executor.execute(
        _task_for(command, tmp_path),
        normalized_params={},
        run_id="watchdog_run",
    )
    return context, context.stages[0].jobs[0]


def test_watchdog_allows_healthy_jobs(sqlite_env, tmp_path: Path) -> None:
    context, job = _run_task(
        tmp_path,
        [
            sys.executable,
            "-u",
            "-c",
            "import time; print('tick-1'); time.sleep(0.2); print('tick-2')",
        ],
    )

    assert context.status == "success"
    assert job.status == "success"
    assert job.watchdog_status == "completed"
    assert job.termination_reason == ""
    assert job.last_output_at is not None


def test_watchdog_terminates_start_timeout(sqlite_env, tmp_path: Path) -> None:
    context, job = _run_task(
        tmp_path,
        [
            sys.executable,
            "-u",
            "-c",
            "import time; time.sleep(2.5)",
        ],
    )

    assert context.status == "failed"
    assert job.status == "failed"
    assert "start timeout" in job.termination_reason.lower()
    assert job.watchdog_status == "terminated"
    assert job.exit_code in (-signal.SIGTERM, -signal.SIGKILL, 143, 137)


def test_watchdog_terminates_stalled_jobs(sqlite_env, tmp_path: Path) -> None:
    context, job = _run_task(
        tmp_path,
        [
            sys.executable,
            "-u",
            "-c",
            "import time; print('boot'); time.sleep(2.5)",
        ],
    )

    assert context.status == "failed"
    assert job.status == "failed"
    assert "stall timeout" in job.termination_reason.lower()
    assert job.watchdog_status == "terminated"
    assert job.last_output_at is not None


def test_watchdog_marks_non_zero_exit_without_timeout(sqlite_env, tmp_path: Path) -> None:
    context, job = _run_task(
        tmp_path,
        [
            sys.executable,
            "-u",
            "-c",
            "import sys; print('boom'); sys.exit(3)",
        ],
    )

    assert context.status == "failed"
    assert job.status == "failed"
    assert job.exit_code == 3
    assert job.watchdog_status == "completed"
    assert job.termination_reason == "boom"


def test_runtime_marks_zero_exit_with_all_detail_failures_as_degraded(
    sqlite_env,
    tmp_path: Path,
) -> None:
    context, job = _run_task(
        tmp_path,
        [
            sys.executable,
            "-u",
            "-c",
            "print('Note details: [None, None, None]')",
        ],
    )

    assert context.status == "degraded"
    assert job.status == "degraded"
    assert job.exit_code == 0
    assert job.watchdog_status == "completed"
    assert "0/3 succeeded" in job.termination_reason


def test_runtime_honors_stage_max_parallel(sqlite_env, tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-u",
        "-c",
        "import time; print('start'); time.sleep(0.4); print('done')",
    ]
    task = TaskSpec(
        slug="watchdog_parallel_limit",
        title="Watchdog Parallel Limit",
        short_desc="parallel",
        capabilities=["test"],
        welcome_lines=["parallel"],
        stages=[
            TaskStage(
                key="parallel_stage",
                name="Parallel Stage",
                jobs=[
                    TaskJob(key=f"job_{index}", name=f"Job {index}", command=command, cwd=tmp_path)
                    for index in range(3)
                ],
                concurrent=True,
                max_parallel=2,
                abort_on_failure=False,
            )
        ],
        aliases=[],
    )

    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=3,
        job_stall_timeout_sec=3,
        terminate_grace_sec=1,
    )
    context = executor.execute(
        task,
        normalized_params={},
        run_id="watchdog_parallel_limit_run",
    )

    assert context.status == "success"
    jobs = context.stages[0].jobs
    assert [job.status for job in jobs] == ["success", "success", "success"]
    assert jobs[2].started_at is not None
    assert jobs[0].started_at is not None
    assert jobs[2].started_at - jobs[0].started_at >= 0.25


def test_runtime_skips_queued_jobs_when_abort_on_failure_is_enabled(sqlite_env, tmp_path: Path) -> None:
    commands = [
        [sys.executable, "-u", "-c", "import sys; print('boom'); sys.exit(2)"],
        [sys.executable, "-u", "-c", "import time; print('wait'); time.sleep(0.4); print('done')"],
        [sys.executable, "-u", "-c", "import time; print('wait'); time.sleep(0.4); print('done')"],
    ]
    task = TaskSpec(
        slug="watchdog_abort_on_failure",
        title="Watchdog Abort On Failure",
        short_desc="parallel",
        capabilities=["test"],
        welcome_lines=["parallel"],
        stages=[
            TaskStage(
                key="parallel_stage",
                name="Parallel Stage",
                jobs=[
                    TaskJob(key=f"job_{index}", name=f"Job {index}", command=command, cwd=tmp_path)
                    for index, command in enumerate(commands)
                ],
                concurrent=True,
                max_parallel=1,
                abort_on_failure=True,
            )
        ],
        aliases=[],
    )

    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=3,
        job_stall_timeout_sec=3,
        terminate_grace_sec=1,
    )
    context = executor.execute(task, normalized_params={}, run_id="watchdog_abort_on_failure_run")

    assert context.status == "failed"
    jobs = context.stages[0].jobs
    assert jobs[0].status == "failed"
    assert jobs[1].status == "skipped"
    assert jobs[2].status == "skipped"


def test_runtime_continues_queued_jobs_when_abort_on_failure_is_disabled(sqlite_env, tmp_path: Path) -> None:
    commands = [
        [sys.executable, "-u", "-c", "import sys; print('boom'); sys.exit(2)"],
        [sys.executable, "-u", "-c", "import time; print('ok-1'); time.sleep(0.1); print('done-1')"],
        [sys.executable, "-u", "-c", "import time; print('ok-2'); time.sleep(0.1); print('done-2')"],
    ]
    task = TaskSpec(
        slug="watchdog_continue_on_failure",
        title="Watchdog Continue On Failure",
        short_desc="parallel",
        capabilities=["test"],
        welcome_lines=["parallel"],
        stages=[
            TaskStage(
                key="parallel_stage",
                name="Parallel Stage",
                jobs=[
                    TaskJob(key=f"job_{index}", name=f"Job {index}", command=command, cwd=tmp_path)
                    for index, command in enumerate(commands)
                ],
                concurrent=True,
                max_parallel=1,
                abort_on_failure=False,
            )
        ],
        aliases=[],
    )

    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=3,
        job_stall_timeout_sec=3,
        terminate_grace_sec=1,
    )
    context = executor.execute(task, normalized_params={}, run_id="watchdog_continue_on_failure_run")

    assert context.status == "failed"
    jobs = context.stages[0].jobs
    assert jobs[0].status == "failed"
    assert jobs[1].status == "success"
    assert jobs[2].status == "success"
