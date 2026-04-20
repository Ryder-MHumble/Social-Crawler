# -*- coding: utf-8 -*-
"""SQLite storage control endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from database.sqlite_storage import get_sqlite_storage

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/sqlite/status")
async def sqlite_status():
    return get_sqlite_storage().get_status()


@router.post("/sqlite/init")
async def init_sqlite():
    return get_sqlite_storage().initialize()
