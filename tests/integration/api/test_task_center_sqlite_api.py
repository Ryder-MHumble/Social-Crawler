from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.task_center import TaskCenterService, get_task_center_service
from config.db_config import sqlite_db_config
from database import sqlite_storage as sqlite_storage_module

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_env(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "task_center.sqlite3"
    monkeypatch.setitem(sqlite_db_config, "db_path", str(db_path))
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)
    storage = sqlite_storage_module.get_sqlite_storage()
    yield storage
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)


@pytest.fixture
def real_service(tmp_path: Path) -> TaskCenterService:
    return TaskCenterService(
        project_root=Path(".").resolve(),
        python_executable=sys.executable,
        state_dir=tmp_path / ".task_center",
    )


@pytest.fixture
def client_with_real_service(real_service: TaskCenterService):
    app.dependency_overrides[get_task_center_service] = lambda: real_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_sqlite_status_init_and_query_routes(
    client_with_real_service: TestClient,
    sqlite_env,
) -> None:
    status_before = client_with_real_service.get("/api/storage/sqlite/status")
    assert status_before.status_code == 200
    assert status_before.json()["initialized"] is False

    init_res = client_with_real_service.post("/api/storage/sqlite/init")
    assert init_res.status_code == 200
    assert init_res.json()["initialized"] is True

    init_again = client_with_real_service.post("/api/storage/sqlite/init")
    assert init_again.status_code == 200
    assert init_again.json()["initialized"] is True

    sqlite_env.record_observation(
        {
            "run_id": "run_sqlite_api",
            "task_slug": "sentiment_monitor",
            "stage_key": "crawl",
            "job_key": "job_xhs",
            "entity_type": "content",
            "platform": "xhs",
            "external_id": "note_1",
            "source_keyword": "openclaw",
            "clean_status": "accepted",
            "clean_reason": "Stored",
            "rule_key": "accepted_content",
            "dedup_fingerprint": "xhs:note_1",
            "snapshot_json": {"title": "OpenClaw note"},
        }
    )
    sqlite_env.record_observation(
        {
            "run_id": "run_sqlite_api",
            "task_slug": "sentiment_monitor",
            "stage_key": "crawl",
            "job_key": "job_xhs",
            "entity_type": "content",
            "platform": "xhs",
            "external_id": "note_2",
            "source_keyword": "openclaw",
            "clean_status": "filtered",
            "clean_reason": "Content failed relevance filter.",
            "rule_key": "filtered_content",
            "dedup_fingerprint": "xhs:note_2",
            "snapshot_json": {"title": "Filtered note"},
        }
    )

    status_after = client_with_real_service.get("/api/storage/sqlite/status")
    assert status_after.status_code == 200
    assert status_after.json()["initialized"] is True
    assert status_after.json()["table_count"] >= 7

    tables_res = client_with_real_service.get("/api/data/sqlite/tables")
    assert tables_res.status_code == 200
    tables_payload = tables_res.json()
    assert "crawl_observations" in tables_payload["supported_tables"]
    assert any(table["name"] == "crawl_observations" for table in tables_payload["tables"])

    stats_res = client_with_real_service.get(
        "/api/data/sqlite/stats",
        params={"run_id": "run_sqlite_api", "task_slug": "sentiment_monitor"},
    )
    assert stats_res.status_code == 200
    stats_payload = stats_res.json()
    assert stats_payload["observation_status_counts"]["accepted"] == 1

    rows_res = client_with_real_service.get(
        "/api/data/sqlite/rows",
        params={
            "table": "crawl_observations",
            "run_id": "run_sqlite_api",
            "task_slug": "sentiment_monitor",
            "platform": "xhs",
            "entity_type": "content",
            "clean_status": "accepted",
            "q": "OpenClaw",
        },
    )
    assert rows_res.status_code == 200
    rows_payload = rows_res.json()
    assert rows_payload["total"] == 1
    row_id = rows_payload["rows"][0]["id"]

    row_res = client_with_real_service.get(
        "/api/data/sqlite/row",
        params={"table": "crawl_observations", "row_id": row_id},
    )
    assert row_res.status_code == 200
    assert row_res.json()["external_id"] == "note_1"

    breakdowns = sqlite_env.get_run_breakdowns("run_sqlite_api")
    assert breakdowns["status_counts"]["accepted"] == 1
    assert breakdowns["status_counts"]["filtered"] == 1
    assert breakdowns["filter_reasons"][0]["reason"] == "Content failed relevance filter."
    assert breakdowns["platform_status_counts"][0]["platform"] == "xhs"
