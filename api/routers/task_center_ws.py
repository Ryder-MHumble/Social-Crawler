from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..services.task_center import TaskCenterService, get_task_center_service

router = APIRouter(tags=["task-center-ws"])


@router.websocket("/ws/runs/active")
async def websocket_active_run(
    websocket: WebSocket,
    service: TaskCenterService = Depends(get_task_center_service),
):
    await websocket.accept()
    last_event_id = 0
    last_heartbeat = time.monotonic()

    try:
        active_run = service.get_active_run()
        if active_run:
            await websocket.send_json({"type": "run_updated", "run": active_run})
            for log_entry in service.get_recent_active_logs():
                await websocket.send_json(
                    {"type": "log", "run_id": active_run["id"], "entry": log_entry}
                )

        while True:
            events = service.get_events_since(last_event_id)
            for event in events:
                await websocket.send_json(event)
                last_event_id = max(last_event_id, int(event["event_id"]))

            if time.monotonic() - last_heartbeat >= 15:
                await websocket.send_json({"type": "heartbeat"})
                last_heartbeat = time.monotonic()

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
    except Exception:
        return
