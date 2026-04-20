#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import shutil
import sys
from pathlib import Path

from database.sqlite_storage import get_sqlite_storage
from tools import runtime_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare runtime/input/openclaw_creators.csv for DM sender.",
    )
    parser.add_argument(
        "--filter",
        default="1",
        help="Whether to run the creator filter after selecting the latest crawler output (1/0).",
    )
    parser.add_argument("--min-follower-count", default="0")
    parser.add_argument("--min-fans-count", dest="min_follower_count", default="0")
    parser.add_argument("--min-total-views", default="0")
    parser.add_argument("--min-total-play-count", dest="min_total_views", default="0")
    parser.add_argument("--max-fans-count", default="0")
    parser.add_argument("--min-average-views", default="0")
    parser.add_argument("--min-total-comment-count", default="0")
    parser.add_argument("--min-total-favorite-count", default="0")
    parser.add_argument("--min-video-count", default="0")
    parser.add_argument("--include-keywords", default="")
    parser.add_argument("--include-profile-keywords", default="")
    parser.add_argument("--include-video-keywords", default="")
    parser.add_argument("--exclude-keywords", default="")
    parser.add_argument("--exclude-profile-keywords", default="")
    parser.add_argument("--exclude-video-keywords", default="")
    parser.add_argument("--creator-whitelist-ids", default="")
    parser.add_argument("--creator-whitelist", default="")
    parser.add_argument("--creator-blacklist-ids", default="")
    parser.add_argument("--creator-blacklist", default="")
    parser.add_argument("--campaign-name", default="openclaw_2026")
    parser.add_argument("--max-targets", default="0")
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
    runtime_paths.ensure_runtime_layout()
    patterns = [
        runtime_paths.get_input_dir() / "openclaw_creators_*.csv",
        project_root / "openclaw_creators_*.csv",
        project_root / "tasks" / "creator_outreach" / "bili_creators_*.csv",
        project_root / "tasks" / "creator_outreach" / "openclaw_creators_*.csv",
    ]
    files: list[Path] = [
        runtime_paths.get_openclaw_csv_path(),
        project_root / "openclaw_creators.csv",
    ]
    for pattern in patterns:
        files.extend(pattern.parent.glob(pattern.name))
    return files


def _count_rows(csv_path: Path) -> int:
    try:
        with csv_path.open("r", encoding="utf-8-sig") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return -1


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except Exception:
        return left == right


def _first_non_empty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    creator_id = _first_non_empty(row, "博主ID", "uid")
    creator_name = _first_non_empty(row, "博主名称", "名称")
    profile_url = _first_non_empty(row, "主页链接", "主页URL")
    bio = _first_non_empty(row, "简介")
    fans = _first_non_empty(row, "粉丝数")
    videos_blob = _first_non_empty(row, "视频列表(标题|URL|播放量|发布日期)")
    representative = [
        _first_non_empty(row, "代表视频1"),
        _first_non_empty(row, "代表视频2"),
        _first_non_empty(row, "代表视频3"),
    ]
    if videos_blob and not any(representative):
        titles = [item.split("|", 1)[0].strip() for item in videos_blob.split(" ;; ") if item.strip()]
        representative = [(titles[index] if index < len(titles) else "") for index in range(3)]
    return {
        "博主ID": creator_id,
        "博主名称": creator_name,
        "主页链接": profile_url,
        "粉丝数": fans,
        "简介": bio,
        "代表视频1": representative[0],
        "代表视频2": representative[1],
        "代表视频3": representative[2],
        "总播放量": _first_non_empty(row, "总播放量"),
        "总评论量": _first_non_empty(row, "总评论量"),
        "总收藏量": _first_non_empty(row, "总收藏量"),
        "平均播放量": _first_non_empty(row, "平均播放量"),
        "视频数量": _first_non_empty(row, "视频数量"),
        "发现关键词": _first_non_empty(row, "发现关键词"),
        "视频列表(标题|URL|播放量|发布日期)": videos_blob,
    }


def _normalize_creator_csv(source: Path, target: Path) -> int:
    with source.open("r", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        rows = [_normalize_row(row) for row in reader]
    fieldnames = [
        "博主ID",
        "博主名称",
        "主页链接",
        "粉丝数",
        "简介",
        "代表视频1",
        "代表视频2",
        "代表视频3",
        "总播放量",
        "总评论量",
        "总收藏量",
        "平均播放量",
        "视频数量",
        "发现关键词",
        "视频列表(标题|URL|播放量|发布日期)",
    ]
    with target.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _env_run_id() -> str:
    return os.getenv("SOCIAL_CRAWLER_RUN_ID", "").strip()


def _merge_csv_text(*values: str) -> str:
    items: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for item in str(raw or "").replace("\n", ",").split(","):
            cleaned = item.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            items.append(cleaned)
    return ",".join(items)


def _import_outreach_candidates(csv_path: Path, campaign_name: str) -> None:
    storage = get_sqlite_storage()
    storage.initialize()
    with csv_path.open("r", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            normalized = _normalize_row(row)
            storage.upsert_outreach_candidate(
                {
                    "campaign_name": campaign_name,
                    "run_id": _env_run_id(),
                    "platform": "bili",
                    "creator_id": normalized.get("博主ID", ""),
                    "creator_name": normalized.get("博主名称", ""),
                    "profile_url": normalized.get("主页链接", ""),
                    "bio": normalized.get("简介", ""),
                    "fans_count": normalized.get("粉丝数", 0),
                    "total_views": normalized.get("总播放量", 0),
                    "average_views": normalized.get("平均播放量", 0),
                    "video_count": normalized.get("视频数量", 0),
                    "representative_videos_json": [
                        normalized.get("代表视频1", ""),
                        normalized.get("代表视频2", ""),
                        normalized.get("代表视频3", ""),
                    ],
                    "discovery_keyword": normalized.get("发现关键词", ""),
                    "filter_status": "discovered",
                    "filter_reason": "",
                    "raw_row_json": normalized,
                }
            )


def _trim_creator_csv(target: Path, max_targets: int) -> int:
    if max_targets <= 0 or not target.exists():
        return _count_rows(target)
    with target.open("r", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    trimmed = rows[:max_targets]
    with target.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trimmed)
    return len(trimmed)


def main() -> int:
    args = _parse_args()
    run_filter = _as_bool(args.filter, default=True)

    project_root = Path(__file__).resolve().parents[2]
    runtime_paths.ensure_runtime_layout()
    runtime_paths.seed_openclaw_csv_from_legacy()
    target = runtime_paths.get_openclaw_csv_path()

    latest_source = _find_latest(_collect_candidate_files(project_root))
    if not latest_source:
        print("No creator CSV found. Run creator discovery first.")
        return 1

    normalized_rows = _normalize_creator_csv(latest_source, target)
    _import_outreach_candidates(target, args.campaign_name)
    runtime_paths.sync_openclaw_csv_to_legacy()
    print(f"Source CSV selected: {latest_source}")
    if _same_file(latest_source, target):
        print(f"Normalized target refreshed in place: {target}")
    else:
        print(f"Normalized and copied to: {target}")
    source_rows = _count_rows(latest_source)
    if source_rows >= 0:
        print(f"Rows in source file: {source_rows}")
    print(f"Rows in normalized target: {normalized_rows}")

    if not run_filter:
        print("Filter step skipped by flag.")
        return 0

    filter_script = project_root / "tasks" / "creator_outreach" / "filter_creators.py"
    if not filter_script.exists():
        print("creator filter script not found, skip filtering.")
        return 0

    print("Running creator filter ...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tasks.creator_outreach.filter_creators",
            str(target),
            "--min-follower-count",
            args.min_follower_count,
            "--min-total-views",
            args.min_total_views,
            "--max-fans-count",
            args.max_fans_count,
            "--min-average-views",
            args.min_average_views,
            "--min-total-comment-count",
            args.min_total_comment_count,
            "--min-total-favorite-count",
            args.min_total_favorite_count,
            "--min-video-count",
            args.min_video_count,
            "--include-keywords",
            _merge_csv_text(args.include_keywords, args.include_profile_keywords, args.include_video_keywords),
            "--exclude-keywords",
            _merge_csv_text(args.exclude_keywords, args.exclude_profile_keywords, args.exclude_video_keywords),
            "--creator-whitelist-ids",
            _merge_csv_text(args.creator_whitelist_ids, args.creator_whitelist),
            "--creator-blacklist-ids",
            _merge_csv_text(args.creator_blacklist_ids, args.creator_blacklist),
            "--campaign-name",
            args.campaign_name,
        ],
        cwd=str(project_root),
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        print("Filtering failed. Keep unfiltered runtime/input/openclaw_creators.csv.")
        return 0

    filtered_files = list(runtime_paths.get_input_dir().glob("openclaw_creators_filtered_*.csv"))
    latest_filtered = _find_latest(filtered_files)
    if not latest_filtered:
        print("Filter script finished but no filtered output file found.")
        return 0

    shutil.copy2(latest_filtered, target)
    runtime_paths.sync_openclaw_csv_to_legacy()
    filtered_rows = _trim_creator_csv(target, int(args.max_targets or "0"))
    print(f"Filtered CSV selected: {latest_filtered}")
    print(f"Updated target file: {target}")
    if filtered_rows >= 0:
        print(f"Rows after filter: {filtered_rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
