from __future__ import annotations

import sys
from pathlib import Path

import config
import pytest

from config.db_config import sqlite_db_config
from database import sqlite_storage as sqlite_storage_module
from database.sqlite_store_base import SQLiteUnifiedStoreBase
from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.runtime import RunSetupError, TaskRuntimeExecutor, serialize_run_context

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_env(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "browsermint_xhs_contract.sqlite3"
    monkeypatch.setitem(sqlite_db_config, "db_path", str(db_path))
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)
    storage = sqlite_storage_module.get_sqlite_storage()
    storage.initialize()
    yield storage
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)


def _task_for(command: list[str], workdir: Path) -> TaskSpec:
    return TaskSpec(
        slug="browsermint_contract_dummy",
        title="Browsermint Contract Dummy",
        short_desc="dummy",
        capabilities=["test"],
        welcome_lines=["browsermint"],
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


def _set_runtime_context(monkeypatch: pytest.MonkeyPatch, *, run_id: str) -> None:
    monkeypatch.setenv("SOCIAL_CRAWLER_RUN_ID", run_id)
    monkeypatch.setenv("SOCIAL_CRAWLER_TASK_SLUG", "sentiment_monitor")
    monkeypatch.setenv("SOCIAL_CRAWLER_STAGE_KEY", "stage_a")
    monkeypatch.setenv("SOCIAL_CRAWLER_JOB_KEY", "job_a")


def test_runtime_marks_degraded_with_zero_detail_hits_after_browsermint_preflight(
    sqlite_env,
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=3,
        job_stall_timeout_sec=3,
        terminate_grace_sec=1,
    )

    def setup_hook(context, event_handler, emit_log, emit_update) -> None:
        emit_log("Connecting Browsermint session bm-session-1.", "info")
        emit_log(
            "Browsermint preflight passed for 1 stage(s); task execution is starting.",
            "info",
        )

    context = executor.execute(
        _task_for(
            [
                sys.executable,
                "-u",
                "-c",
                'print("Note details: [None, None]")',
            ],
            tmp_path,
        ),
        normalized_params={"browser_provider": "browsermint", "platforms": ["xhs"]},
        run_id="browsermint_detail_degraded",
        event_handler=events.append,
        setup_hook=setup_hook,
    )

    snapshot = serialize_run_context(context)
    run_updates = [event["run"] for event in events if event["type"] == "run_updated"]
    log_entries = [event["entry"] for event in events if event["type"] == "log"]

    assert run_updates[0]["status"] == "preflight"
    assert run_updates[0]["lifecycle"]["phase"] == "preflight"
    assert any(
        run["status"] == "running" and run["lifecycle"]["phase"] == "running"
        for run in run_updates
    )
    assert snapshot["status"] == "degraded"
    assert snapshot["lifecycle"]["phase"] == "finalizing"
    assert snapshot["metrics"]["stalled_jobs"] == 0
    assert snapshot["metrics"]["detail_requests"] == 2
    assert snapshot["metrics"]["detail_successes"] == 0
    assert snapshot["metrics"]["detail_failures"] == 2
    assert snapshot["metrics"]["degraded_jobs"] == 1
    assert snapshot["warnings"][0]["code"] == "detail_failure_ratio_high"
    assert any(
        entry["stage_key"] == "__system__"
        and entry["job_key"] == "preflight"
        and "Browsermint preflight passed" in entry["message"]
        for entry in log_entries
    )


def test_runtime_waiting_user_preflight_serializes_issue_summary(
    sqlite_env,
    tmp_path: Path,
) -> None:
    events: list[dict[str, object]] = []
    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=3,
        job_stall_timeout_sec=3,
        terminate_grace_sec=1,
    )

    def setup_hook(context, event_handler, emit_log, emit_update) -> None:
        emit_log("Connecting Browsermint session bm-session-2.", "info")
        raise RunSetupError(
            "Browsermint session unauthorized 403",
            status="waiting_user",
            level="warning",
        )

    context = executor.execute(
        _task_for(
            [sys.executable, "-u", "-c", "print('should-not-run')"],
            tmp_path,
        ),
        normalized_params={"browser_provider": "browsermint", "platforms": ["xhs"]},
        run_id="browsermint_waiting_user",
        event_handler=events.append,
        setup_hook=setup_hook,
    )

    snapshot = serialize_run_context(context)
    run_updates = [event["run"] for event in events if event["type"] == "run_updated"]
    log_entries = [event["entry"] for event in events if event["type"] == "log"]

    assert context.status == "waiting_user"
    assert run_updates[0]["lifecycle"]["phase"] == "preflight"
    assert run_updates[-1]["status"] == "waiting_user"
    assert snapshot["lifecycle"]["phase"] == "waiting_user"
    assert snapshot["lifecycle"]["label"] == "Waiting For User"
    assert snapshot["issues"][0]["category_key"] == "auth"
    assert snapshot["issues"][0]["count"] == 1
    assert all(stage["status"] == "waiting" for stage in snapshot["stages"])
    assert any(
        entry["stage_key"] == "__system__"
        and entry["job_key"] == "preflight"
        and entry["message"] == "Browsermint session unauthorized 403"
        for entry in log_entries
    )


def test_xhs_official_accounts_bypass_runtime_filters(sqlite_env, monkeypatch) -> None:
    monkeypatch.setattr(config, "ENABLE_RELEVANCE_FILTER", True, raising=False)
    monkeypatch.setattr(config, "RELEVANCE_MUST_CONTAIN", ["openclaw"], raising=False)
    monkeypatch.setattr(config, "RELEVANCE_EXCLUDE_KEYWORDS", [], raising=False)
    monkeypatch.setattr(config, "MIN_CONTENT_ENGAGEMENT", 100, raising=False)

    base = SQLiteUnifiedStoreBase("xhs")

    _set_runtime_context(monkeypatch, run_id="run_regular_relevance")
    base.save_content(
        {
            "content_id": "regular-relevance",
            "title": "irrelevant title",
            "description": "still irrelevant",
            "liked_count": 999,
            "comment_count": 1,
            "source_keyword": "openclaw",
        }
    )

    _set_runtime_context(monkeypatch, run_id="run_official_relevance")
    base.save_content(
        {
            "content_id": "official-relevance",
            "title": "irrelevant title",
            "description": "still irrelevant",
            "liked_count": 999,
            "comment_count": 1,
            "source_keyword": "@OpenClaw官方号",
        }
    )

    _set_runtime_context(monkeypatch, run_id="run_regular_engagement")
    base.save_content(
        {
            "content_id": "regular-engagement",
            "title": "openclaw update",
            "description": "contains required keyword",
            "liked_count": 1,
            "comment_count": 1,
            "source_keyword": "openclaw",
        }
    )

    _set_runtime_context(monkeypatch, run_id="run_official_engagement")
    base.save_content(
        {
            "content_id": "official-engagement",
            "title": "openclaw update",
            "description": "contains required keyword",
            "liked_count": 1,
            "comment_count": 1,
            "source_keyword": "@OpenClaw官方号",
        }
    )

    observations = sqlite_env.query_rows(
        table="crawl_observations",
        entity_type="content",
        limit=20,
    )
    rows_by_run = {row["run_id"]: row for row in observations["rows"]}

    assert rows_by_run["run_regular_relevance"]["clean_status"] == "filtered"
    assert rows_by_run["run_regular_relevance"]["clean_reason"] == "Content failed relevance filter."
    assert rows_by_run["run_official_relevance"]["clean_status"] == "accepted"
    assert rows_by_run["run_regular_engagement"]["clean_status"] == "filtered"
    assert "below 100" in rows_by_run["run_regular_engagement"]["clean_reason"]
    assert rows_by_run["run_official_engagement"]["clean_status"] == "accepted"


def test_serialize_run_context_preserves_stalled_jobs_metric(
    sqlite_env,
    tmp_path: Path,
) -> None:
    executor = TaskRuntimeExecutor(
        project_root=tmp_path,
        logs_root=tmp_path / "logs",
        refresh_seconds=0.05,
        job_start_timeout_sec=1,
        job_stall_timeout_sec=1,
        terminate_grace_sec=1,
    )
    context = executor.execute(
        _task_for(
            [
                sys.executable,
                "-u",
                "-c",
                "import time; print('boot'); time.sleep(2.5)",
            ],
            tmp_path,
        ),
        normalized_params={},
        run_id="browsermint_stalled_metric",
    )

    snapshot = serialize_run_context(context)

    assert context.status == "failed"
    assert snapshot["metrics"]["stalled_jobs"] == 1
    assert snapshot["metrics"]["candidate_count"] == 0
    assert snapshot["metrics"]["detail_requests"] == 0
    assert snapshot["metrics"]["detail_successes"] == 0
    assert snapshot["metrics"]["detail_failures"] == 0
