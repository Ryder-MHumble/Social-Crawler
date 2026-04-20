from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.task_center import TaskCenterService, get_task_center_service
from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskTemplate

pytestmark = pytest.mark.integration


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _build_dummy_definition() -> TaskDefinition:
    template = TaskTemplate(
        slug="dummy_task",
        title="Dummy Task",
        description="A tiny task used for API tests.",
        defaults={"sleep_seconds": 1.0},
        capabilities=["test"],
        fields=[
            TaskField(
                key="sleep_seconds",
                component="number",
                label="Sleep Seconds",
                default=1.0,
                group="General",
            )
        ],
    )

    def normalize(raw_params):
        raw = dict(raw_params or {})
        value = float(raw.get("sleep_seconds", 1.0))
        if value <= 0:
            raise ValueError("sleep_seconds must be positive")
        return {"sleep_seconds": value}

    def build_task(project_root: Path, python_executable: str, params=None) -> TaskSpec:
        normalized = normalize(params)
        command = [
            python_executable,
            "-c",
            (
                "import time; "
                "print('dummy-start'); "
                f"time.sleep({normalized['sleep_seconds']}); "
                "print('dummy-done')"
            ),
        ]
        stage = TaskStage(
            key="dummy_stage",
            name="Dummy Stage",
            jobs=[
                TaskJob(
                    key="dummy_job",
                    name="Dummy Job",
                    command=command,
                    cwd=project_root,
                )
            ],
            concurrent=False,
            abort_on_failure=False,
        )
        return TaskSpec(
            slug="dummy_task",
            title="Dummy Task",
            short_desc="Dummy",
            capabilities=["test"],
            welcome_lines=["dummy"],
            stages=[stage],
            aliases=[],
        )

    return TaskDefinition(
        template=template,
        normalize_params=normalize,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id="preset_dummy_default",
                task_slug="dummy_task",
                name="Dummy Default",
                params={"sleep_seconds": 1.0},
                is_default=True,
            )
        ],
    )


@pytest.fixture
def real_service(tmp_path: Path) -> TaskCenterService:
    service = TaskCenterService(
        project_root=Path(".").resolve(),
        python_executable=sys.executable,
        state_dir=tmp_path / ".task_center",
    )
    return service


@pytest.fixture
def dummy_service(tmp_path: Path) -> TaskCenterService:
    service = TaskCenterService(
        project_root=tmp_path,
        python_executable=sys.executable,
        definitions=[_build_dummy_definition()],
        state_dir=tmp_path / ".task_center",
    )
    yield service
    service.stop_active_run()
    _wait_until(lambda: service.get_active_run() is None, timeout=3.0)


@pytest.fixture
def client_with_real_service(real_service: TaskCenterService):
    app.dependency_overrides[get_task_center_service] = lambda: real_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_dummy_service(dummy_service: TaskCenterService):
    app.dependency_overrides[get_task_center_service] = lambda: dummy_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_task_and_preset_crud(client_with_real_service: TestClient) -> None:
    tasks_res = client_with_real_service.get("/api/tasks")
    assert tasks_res.status_code == 200
    task_slugs = [item["slug"] for item in tasks_res.json()["tasks"]]
    assert {"sentiment_monitor", "creator_outreach", "vibe_coding"}.issubset(task_slugs)

    preview_res = client_with_real_service.post(
        "/api/tasks/sentiment_monitor/preview",
        json={"preset_id": "preset_sentiment_xhs_posts_only", "params": {}},
    )
    assert preview_res.status_code == 200
    preview_payload = preview_res.json()
    assert preview_payload["normalized_params"]["platforms"] == ["xhs"]
    assert preview_payload["spec"]["stages"][0]["key"] == "sentiment_keyword_parallel_crawl"

    creator_preview_res = client_with_real_service.post(
        "/api/tasks/creator_outreach/preview",
        json={"preset_id": "preset_creator_campaign_dry_run", "params": {}},
    )
    assert creator_preview_res.status_code == 200
    creator_payload = creator_preview_res.json()
    assert creator_payload["normalized_params"]["run_dm"] is True
    assert creator_payload["spec"]["stages"][-1]["key"] == "dm_campaign"

    vibe_preview_res = client_with_real_service.post(
        "/api/tasks/vibe_coding/preview",
        json={"preset_id": "preset_vibe_creator_targets", "params": {}},
    )
    assert vibe_preview_res.status_code == 200
    vibe_payload = vibe_preview_res.json()
    assert vibe_payload["normalized_params"]["enable_account_crawl"] is True
    assert vibe_payload["spec"]["stages"][0]["key"] == "vibe_creator_parallel_crawl"

    create_res = client_with_real_service.post(
        "/api/presets",
        json={
            "task_slug": "sentiment_monitor",
            "name": "测试预设",
            "params": {
                "platforms": ["xhs"],
                "keywords": "测试关键词",
                "max_notes_count": 12,
                "enable_comments": False,
                "enable_sub_comments": False,
                "max_comments_count_singlenotes": 20,
                "login_type": "qrcode",
                "save_option": "json",
                "headless": False,
            },
            "is_default": False,
        },
    )
    assert create_res.status_code == 200
    preset_id = create_res.json()["id"]

    update_res = client_with_real_service.put(
        f"/api/presets/{preset_id}",
        json={
            "name": "测试预设-更新",
            "params": {
                "platforms": ["xhs"],
                "keywords": "更新关键词",
                "max_notes_count": 18,
                "enable_comments": False,
                "enable_sub_comments": False,
                "max_comments_count_singlenotes": 20,
                "login_type": "qrcode",
                "save_option": "json",
                "headless": False,
            },
            "is_default": False,
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "测试预设-更新"

    delete_res = client_with_real_service.delete(f"/api/presets/{preset_id}")
    assert delete_res.status_code == 200


def test_run_start_stop_and_single_active_limit(
    client_with_dummy_service: TestClient,
    dummy_service: TaskCenterService,
) -> None:
    start_res = client_with_dummy_service.post(
        "/api/runs",
        json={"task_slug": "dummy_task", "params": {"sleep_seconds": 2.0}},
    )
    assert start_res.status_code == 200
    run_id = start_res.json()["id"]

    second_start_res = client_with_dummy_service.post(
        "/api/runs",
        json={"task_slug": "dummy_task", "params": {"sleep_seconds": 2.0}},
    )
    assert second_start_res.status_code == 400

    active_res = client_with_dummy_service.get("/api/runs/active")
    assert active_res.status_code == 200
    assert active_res.json()["run"]["id"] == run_id

    stop_res = client_with_dummy_service.post("/api/runs/active/stop")
    assert stop_res.status_code == 200
    assert _wait_until(lambda: dummy_service.get_active_run() is None, timeout=4.0)

    runs_res = client_with_dummy_service.get("/api/runs")
    assert runs_res.status_code == 200
    assert runs_res.json()["runs"][0]["id"] == run_id


def test_active_run_websocket_stream(
    client_with_dummy_service: TestClient,
    dummy_service: TaskCenterService,
) -> None:
    run = dummy_service.start_run(
        task_slug="dummy_task",
        params={"sleep_seconds": 1.0},
        preset_id="preset_dummy_default",
    )
    assert _wait_until(lambda: len(dummy_service.get_recent_active_logs()) > 0, timeout=4.0)

    with client_with_dummy_service.websocket_connect("/api/ws/runs/active") as websocket:
        first = websocket.receive_json()
        assert first["type"] == "run_updated"
        assert first["run"]["id"] == run["id"]
        first_job = first["run"]["stages"][0]["jobs"][0]
        assert "watchdog_status" in first_job
        assert "last_output_at" in first_job
        assert "termination_reason" in first_job

        second = websocket.receive_json()
        assert second["type"] == "log"
        assert second["run_id"] == run["id"]

    dummy_service.stop_active_run()
    _wait_until(lambda: dummy_service.get_active_run() is None, timeout=4.0)
