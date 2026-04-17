#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import runtime_paths


def _merge_move(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if target.exists() and child.is_dir() and target.is_dir():
            _merge_move(child, target)
            continue
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
    try:
        src.rmdir()
    except OSError:
        pass


def main() -> int:
    repo_root = runtime_paths.get_repo_root()
    runtime_paths.ensure_runtime_layout()

    archive_root = repo_root / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)

    mappings = [
        (repo_root / "browser_data", runtime_paths.get_browser_data_dir()),
        (repo_root / "data", runtime_paths.get_data_dir()),
        (repo_root / "logs", runtime_paths.get_logs_dir()),
        (repo_root / ".task_center", runtime_paths.get_task_center_state_dir()),
        (repo_root / ".backup", archive_root / ".backup"),
        (repo_root / "run_parallel_snapshot_550", archive_root / "run_parallel_snapshot_550"),
    ]
    for src, dst in mappings:
        _merge_move(src, dst)

    for filename in ("run_parallel_full.log", "run_parallel_live.log", "dm_send_log.txt"):
        src = repo_root / filename
        if not src.exists():
            continue
        shutil.move(str(src), str(archive_root / filename))

    runtime_csv = runtime_paths.get_openclaw_csv_path()
    legacy_csv = runtime_paths.get_legacy_openclaw_csv_path()
    if legacy_csv.exists() and not runtime_csv.exists():
        runtime_csv.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_csv, runtime_csv)
    runtime_paths.sync_openclaw_csv_to_legacy()

    print(f"runtime directory ready: {runtime_paths.get_runtime_dir()}")
    print(f"archive directory ready: {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
