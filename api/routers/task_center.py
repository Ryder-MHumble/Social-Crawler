from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas.task_center import (
    TaskPreviewRequest,
    TaskPresetCreateRequest,
    TaskPresetUpdateRequest,
    TaskRunStartRequest,
)
from ..services.task_center import TaskCenterService, get_task_center_service

router = APIRouter(tags=["task-center"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/tasks")
async def list_tasks(service: TaskCenterService = Depends(get_task_center_service)):
    return {"tasks": service.list_templates()}


@router.get("/tasks/{slug}")
async def get_task(slug: str, service: TaskCenterService = Depends(get_task_center_service)):
    try:
        return service.get_template(slug)
    except Exception as exc:  # pragma: no cover - fastapi plumbing
        raise _handle_error(exc) from exc


@router.post("/tasks/{slug}/preview")
async def preview_task(
    slug: str,
    request: TaskPreviewRequest,
    service: TaskCenterService = Depends(get_task_center_service),
):
    try:
        return service.preview_task(slug, params=request.params, preset_id=request.preset_id)
    except Exception as exc:  # pragma: no cover - fastapi plumbing
        raise _handle_error(exc) from exc


@router.get("/presets")
async def list_presets(
    task_slug: str | None = None,
    service: TaskCenterService = Depends(get_task_center_service),
):
    return {"presets": service.list_presets(task_slug=task_slug)}


@router.post("/presets")
async def create_preset(
    request: TaskPresetCreateRequest,
    service: TaskCenterService = Depends(get_task_center_service),
):
    try:
        preset = service.create_preset(
            task_slug=request.task_slug,
            name=request.name,
            params=request.params,
            is_default=request.is_default,
        )
        return preset
    except Exception as exc:  # pragma: no cover - fastapi plumbing
        raise _handle_error(exc) from exc


@router.put("/presets/{preset_id}")
async def update_preset(
    preset_id: str,
    request: TaskPresetUpdateRequest,
    service: TaskCenterService = Depends(get_task_center_service),
):
    try:
        preset = service.update_preset(
            preset_id,
            name=request.name,
            params=request.params,
            is_default=request.is_default,
        )
        return preset
    except Exception as exc:  # pragma: no cover - fastapi plumbing
        raise _handle_error(exc) from exc


@router.delete("/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    service: TaskCenterService = Depends(get_task_center_service),
):
    if not service.delete_preset(preset_id):
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"status": "ok"}


@router.get("/runs")
async def list_runs(service: TaskCenterService = Depends(get_task_center_service)):
    return {"runs": service.list_runs()}


@router.post("/runs")
async def start_run(
    request: TaskRunStartRequest,
    service: TaskCenterService = Depends(get_task_center_service),
):
    try:
        run = service.start_run(
            task_slug=request.task_slug,
            params=request.params,
            preset_id=request.preset_id,
        )
        return run
    except Exception as exc:  # pragma: no cover - fastapi plumbing
        raise _handle_error(exc) from exc


@router.get("/runs/active")
async def get_active_run(service: TaskCenterService = Depends(get_task_center_service)):
    return {"run": service.get_active_run()}


@router.post("/runs/active/stop")
async def stop_active_run(service: TaskCenterService = Depends(get_task_center_service)):
    run = service.stop_active_run()
    if not run:
        raise HTTPException(status_code=400, detail="No task is running")
    return {"status": "ok", "run": run}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, service: TaskCenterService = Depends(get_task_center_service)):
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    limit: int = 200,
    service: TaskCenterService = Depends(get_task_center_service),
):
    return {"logs": service.get_run_logs(run_id, limit=limit)}
