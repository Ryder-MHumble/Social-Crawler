#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare root-level openclaw_creators.csv for DM sender.",
    )
    parser.add_argument(
        "--filter",
        default="1",
        help="Whether to run filter_ai_creators.py after selecting latest crawler output (1/0).",
    )
    return parser.parse_args()


def _as_bool(raw: str, default: bool = True) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _find_latest(candidates: list[Path]) -> Path | None:
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _collect_candidate_files(project_root: Path) -> list[Path]:
    patterns = [
        project_root / "openclaw_creators_*.csv",
        project_root / "scripts" / "bili_creator_crawler" / "bili_creators_*.csv",
        project_root / "scripts" / "bili_creator_crawler" / "openclaw_creators_*.csv",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(pattern.parent.glob(pattern.name))
    return files


def _count_rows(csv_path: Path) -> int:
    try:
        with csv_path.open("r", encoding="utf-8-sig") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return -1


def main() -> int:
    args = _parse_args()
    run_filter = _as_bool(args.filter, default=True)

    project_root = Path(__file__).resolve().parents[2]
    target = project_root / "openclaw_creators.csv"

    latest_source = _find_latest(_collect_candidate_files(project_root))
    if not latest_source:
        print("No creator CSV found. Run creator discovery first.")
        return 1

    shutil.copy2(latest_source, target)
    source_rows = _count_rows(latest_source)
    print(f"Source CSV selected: {latest_source}")
    print(f"Copied to: {target}")
    if source_rows >= 0:
        print(f"Rows in source file: {source_rows}")

    if not run_filter:
        print("Filter step skipped by flag.")
        return 0

    filter_script = project_root / "filter_ai_creators.py"
    if not filter_script.exists():
        print("filter_ai_creators.py not found, skip filtering.")
        return 0

    print("Running filter_ai_creators.py ...")
    result = subprocess.run(
        [sys.executable, str(filter_script), str(target)],
        cwd=str(project_root),
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        print("Filtering failed. Keep unfiltered openclaw_creators.csv.")
        return 0

    filtered_files = list(project_root.glob("openclaw_creators_filtered_*.csv"))
    latest_filtered = _find_latest(filtered_files)
    if not latest_filtered:
        print("Filter script finished but no filtered output file found.")
        return 0

    shutil.copy2(latest_filtered, target)
    filtered_rows = _count_rows(latest_filtered)
    print(f"Filtered CSV selected: {latest_filtered}")
    print(f"Updated target file: {target}")
    if filtered_rows >= 0:
        print(f"Rows after filter: {filtered_rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

