# -*- coding: utf-8 -*-
"""Centralized runtime path resolver for Social-Crawler."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve(env_name: str, default: Path) -> Path:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    return Path(raw).expanduser()


def get_repo_root() -> Path:
    return REPO_ROOT


def get_repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def get_runtime_dir() -> Path:
    return _resolve("SOCIAL_CRAWLER_RUNTIME_DIR", get_repo_path("runtime"))


def get_data_dir() -> Path:
    return _resolve("SOCIAL_CRAWLER_DATA_DIR", get_runtime_dir() / "data")


def get_browser_data_dir() -> Path:
    return _resolve("SOCIAL_CRAWLER_BROWSER_DATA_DIR", get_runtime_dir() / "browser_data")


def get_logs_dir() -> Path:
    return get_runtime_dir() / "logs"


def get_task_runs_dir() -> Path:
    return get_logs_dir() / "task_runs"


def get_task_center_state_dir() -> Path:
    return get_runtime_dir() / "task_center_state"


def get_input_dir() -> Path:
    return get_runtime_dir() / "input"


def get_webui_dir() -> Path:
    return _resolve("SOCIAL_CRAWLER_WEBUI_DIR", get_runtime_dir() / "webui")


def get_legacy_webui_dir() -> Path:
    return get_repo_path("api", "webui")


def get_webui_dir_with_fallback() -> Path:
    runtime_webui = get_webui_dir()
    if runtime_webui.exists():
        return runtime_webui
    return get_legacy_webui_dir()


def get_browser_user_data_dir(platform: str, user_data_pattern: str, *, cdp: bool = False) -> Path:
    pattern = user_data_pattern if "%s" in user_data_pattern else f"{user_data_pattern}_%s"
    folder = pattern % platform
    if cdp:
        folder = f"cdp_{folder}"
    return get_browser_data_dir() / folder


def get_openclaw_csv_path() -> Path:
    return get_input_dir() / "openclaw_creators.csv"


def get_legacy_openclaw_csv_path() -> Path:
    return get_repo_path("openclaw_creators.csv")


def ensure_runtime_layout() -> None:
    for path in (
        get_runtime_dir(),
        get_browser_data_dir(),
        get_data_dir(),
        get_logs_dir(),
        get_task_runs_dir(),
        get_task_center_state_dir(),
        get_input_dir(),
        get_webui_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)


def sync_openclaw_csv_to_legacy() -> None:
    src = get_openclaw_csv_path()
    dst = get_legacy_openclaw_csv_path()
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def seed_openclaw_csv_from_legacy() -> None:
    src = get_legacy_openclaw_csv_path()
    dst = get_openclaw_csv_path()
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
