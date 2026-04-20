#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filter noisy or low-signal creators from outreach CSV and sync results to SQLite."""

from __future__ import annotations

import argparse
import csv
import os
import re
from datetime import datetime
from typing import Iterable

from database.sqlite_storage import get_sqlite_storage
from tools import runtime_paths

NOISE_VIDEO_KEYWORDS = [
    "小龙虾我先吃",
    "小龙虾吃",
    "吃小龙虾",
    "麻辣小龙虾",
    "清炒小龙虾",
    "今夏第一顿",
    "口味虾",
    "龙虾肉质",
    "选股小龙虾版",
    "Z哥选股",
    "炒股Python",
    "原神日常",
    "福特号起火",
    "中东战事",
    "Comfyui.*wan2",
    "SD整合包.*大尺度",
]
NOISE_CREATOR_IDS = {
    "1244310984",
    "479503119",
    "3546977568557453",
    "3546851764603794",
    "34528864",
    "385941246",
}
DEFAULT_AI_KEYWORDS = [
    "openclaw",
    "openclaws",
    "小龙虾",
    "龙虾",
    "养虾",
    "clawdbot",
    "agent",
    "skill",
    "mcp",
    "ai",
    "人工智能",
    "大模型",
    "token",
    "部署",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "qwen",
    "qclaw",
    "workbuddy",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter creator outreach CSV.")
    parser.add_argument("input_file", nargs="?", default="")
    parser.add_argument("--min-follower-count", type=int, default=0)
    parser.add_argument("--min-fans-count", dest="min_follower_count", type=int, default=0)
    parser.add_argument("--max-fans-count", type=int, default=0)
    parser.add_argument("--min-total-views", type=int, default=0)
    parser.add_argument("--min-total-play-count", dest="min_total_views", type=int, default=0)
    parser.add_argument("--min-average-views", type=int, default=0)
    parser.add_argument("--min-total-comment-count", type=int, default=0)
    parser.add_argument("--min-total-favorite-count", type=int, default=0)
    parser.add_argument("--min-video-count", type=int, default=0)
    parser.add_argument("--include-keywords", default="")
    parser.add_argument("--exclude-keywords", default="")
    parser.add_argument("--creator-whitelist-ids", default="")
    parser.add_argument("--creator-whitelist", dest="creator_whitelist_ids", default="")
    parser.add_argument("--creator-blacklist-ids", default="")
    parser.add_argument("--creator-blacklist", dest="creator_blacklist_ids", default="")
    parser.add_argument("--campaign-name", default="openclaw_2026")
    return parser.parse_args()


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").replace("\n", ",").split(",") if item.strip()]


def _first_non_empty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _as_int(raw: str) -> int:
    try:
        return int(float(str(raw or "0").strip()))
    except (TypeError, ValueError):
        return 0


def _env_context() -> dict[str, str]:
    return {
        "run_id": os.getenv("SOCIAL_CRAWLER_RUN_ID", "").strip(),
        "task_slug": os.getenv("SOCIAL_CRAWLER_TASK_SLUG", "").strip(),
        "stage_key": os.getenv("SOCIAL_CRAWLER_STAGE_KEY", "").strip(),
        "job_key": os.getenv("SOCIAL_CRAWLER_JOB_KEY", "").strip(),
    }


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    video_blob = _first_non_empty(row, "视频列表(标题|URL|播放量|发布日期)")
    representative = [
        _first_non_empty(row, "代表视频1"),
        _first_non_empty(row, "代表视频2"),
        _first_non_empty(row, "代表视频3"),
    ]
    if video_blob and not any(representative):
        titles = [part.split("|", 1)[0].strip() for part in video_blob.split(" ;; ") if part.strip()]
        representative = [(titles[index] if index < len(titles) else "") for index in range(3)]
    return {
        "博主ID": _first_non_empty(row, "博主ID", "uid"),
        "博主名称": _first_non_empty(row, "博主名称", "名称"),
        "主页链接": _first_non_empty(row, "主页链接", "主页URL"),
        "粉丝数": _first_non_empty(row, "粉丝数"),
        "简介": _first_non_empty(row, "简介"),
        "代表视频1": representative[0],
        "代表视频2": representative[1],
        "代表视频3": representative[2],
        "总播放量": _first_non_empty(row, "总播放量"),
        "总评论量": _first_non_empty(row, "总评论量"),
        "总收藏量": _first_non_empty(row, "总收藏量"),
        "平均播放量": _first_non_empty(row, "平均播放量"),
        "视频数量": _first_non_empty(row, "视频数量"),
        "发现关键词": _first_non_empty(row, "发现关键词"),
        "视频列表(标题|URL|播放量|发布日期)": video_blob,
    }


def _video_texts(row: dict[str, str]) -> list[str]:
    return [
        row.get("代表视频1", ""),
        row.get("代表视频2", ""),
        row.get("代表视频3", ""),
        row.get("视频列表(标题|URL|播放量|发布日期)", ""),
    ]


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords if keyword.strip())


def is_noise_by_video(video_title: str) -> bool:
    for kw in NOISE_VIDEO_KEYWORDS:
        if re.search(kw, video_title):
            return True
    return False


def _candidate_payload(
    row: dict[str, str],
    *,
    campaign_name: str,
    filter_status: str,
    filter_reason: str,
) -> dict[str, object]:
    return {
        "campaign_name": campaign_name,
        "run_id": _env_context()["run_id"],
        "platform": "bili",
        "creator_id": row.get("博主ID", ""),
        "creator_name": row.get("博主名称", ""),
        "profile_url": row.get("主页链接", ""),
        "bio": row.get("简介", ""),
        "fans_count": _as_int(row.get("粉丝数", "0")),
        "total_views": _as_int(row.get("总播放量", "0")),
        "average_views": _as_int(row.get("平均播放量", "0")),
        "video_count": _as_int(row.get("视频数量", "0")),
        "representative_videos_json": _video_texts(row)[:3],
        "discovery_keyword": row.get("发现关键词", ""),
        "filter_status": filter_status,
        "filter_reason": filter_reason,
        "raw_row_json": row,
    }


def _record_creator_observation(
    storage,
    *,
    row: dict[str, str],
    clean_status: str,
    clean_reason: str,
    rule_key: str,
) -> None:
    creator_id = row.get("博主ID", "")
    if not creator_id:
        return
    storage.record_observation(
        {
            **_env_context(),
            "entity_type": "creator",
            "platform": "bili",
            "external_id": creator_id,
            "source_keyword": row.get("发现关键词", ""),
            "clean_status": clean_status,
            "clean_reason": clean_reason,
            "rule_key": rule_key,
            "dedup_fingerprint": f"bili:{creator_id}",
            "snapshot_json": row,
        }
    )


def filter_creators(args: argparse.Namespace) -> None:
    input_file = args.input_file or str(runtime_paths.get_openclaw_csv_path())
    whitelist = set(_split_csv(args.creator_whitelist_ids))
    blacklist = set(_split_csv(args.creator_blacklist_ids)) | set(NOISE_CREATOR_IDS)
    include_keywords = _split_csv(args.include_keywords)
    exclude_keywords = _split_csv(args.exclude_keywords)
    storage = get_sqlite_storage()
    storage.initialize()

    rows: list[dict[str, str]] = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(_normalize_row(row))

    filtered: list[dict[str, str]] = []
    removed: list[tuple[str, str, str]] = []
    fieldnames = list(rows[0].keys()) if rows else [
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

    for row in rows:
        creator_id = row["博主ID"]
        name = row["博主名称"]
        videos = _video_texts(row)
        all_videos = " ".join(videos).lower()
        profile_text = " ".join(
            part for part in [row.get("博主名称", ""), row.get("简介", ""), row.get("发现关键词", "")] if part
        ).lower()
        total_play = _as_int(row.get("总播放量", "0"))
        total_comment = _as_int(row.get("总评论量", "0"))
        total_favorite = _as_int(row.get("总收藏量", "0"))
        average_play = _as_int(row.get("平均播放量", "0"))
        fans = _as_int(row.get("粉丝数", "0"))
        video_count = _as_int(row.get("视频数量", "0"))

        filter_status = "accepted"
        filter_reason = "Passed creator outreach filters."
        rule_key = "accepted_creator_outreach"

        if creator_id in blacklist:
            filter_status = "filtered"
            filter_reason = "黑名单/噪音创作者"
            rule_key = "creator_blacklist"
        elif creator_id in whitelist:
            filter_status = "accepted"
            filter_reason = "命中白名单"
            rule_key = "creator_whitelist"
        elif fans < args.min_follower_count:
            filter_status = "filtered"
            filter_reason = "粉丝数不足"
            rule_key = "min_fans"
        elif args.max_fans_count and fans > args.max_fans_count:
            filter_status = "filtered"
            filter_reason = "粉丝数超过上限"
            rule_key = "max_fans"
        elif total_play < args.min_total_views:
            filter_status = "filtered"
            filter_reason = "总播放量不足"
            rule_key = "min_total_views"
        elif average_play < args.min_average_views:
            filter_status = "filtered"
            filter_reason = "平均播放量不足"
            rule_key = "min_average_views"
        elif total_comment < args.min_total_comment_count:
            filter_status = "filtered"
            filter_reason = "总评论量不足"
            rule_key = "min_total_comment"
        elif total_favorite < args.min_total_favorite_count:
            filter_status = "filtered"
            filter_reason = "总收藏量不足"
            rule_key = "min_total_favorite"
        elif video_count < args.min_video_count:
            filter_status = "filtered"
            filter_reason = "视频数量不足"
            rule_key = "min_video_count"
        elif not any(video.strip() for video in videos):
            filter_status = "filtered"
            filter_reason = "无视频数据"
            rule_key = "missing_videos"
        elif any(is_noise_by_video(video) for video in videos if video.strip()):
            filter_status = "filtered"
            filter_reason = "视频命中噪音规则"
            rule_key = "noise_video"
        elif exclude_keywords and (
            _contains_any(all_videos, exclude_keywords) or _contains_any(profile_text, exclude_keywords)
        ):
            filter_status = "filtered"
            filter_reason = "命中排除词"
            rule_key = "exclude_keywords"
        else:
            required_keywords = include_keywords or DEFAULT_AI_KEYWORDS
            if required_keywords and not (
                _contains_any(all_videos, required_keywords)
                or _contains_any(profile_text, required_keywords)
            ):
                filter_status = "filtered"
                filter_reason = "内容与目标主题无关"
                rule_key = "topic_match"

        storage.upsert_outreach_candidate(
            _candidate_payload(
                row,
                campaign_name=args.campaign_name,
                filter_status=filter_status,
                filter_reason=filter_reason,
            )
        )

        if filter_status == "accepted":
            existed = storage.has_creator(platform="bili", user_id=creator_id)
            storage.upsert_creator(
                {
                    "platform": "bili",
                    "user_id": creator_id,
                    "nickname": name,
                    "avatar": "",
                    "description": row.get("简介", ""),
                    "gender": "",
                    "ip_location": "",
                    "follows_count": 0,
                    "fans_count": fans,
                    "interaction_count": total_play + total_comment + total_favorite,
                    "platform_payload_json": {
                        "profile_url": row.get("主页链接", ""),
                        "representative_videos": videos[:3],
                        "total_views": total_play,
                        "total_comments": total_comment,
                        "total_favorites": total_favorite,
                        "video_count": video_count,
                        "discovery_keyword": row.get("发现关键词", ""),
                    },
                }
            )
            _record_creator_observation(
                storage,
                row=row,
                clean_status="deduped" if existed else "accepted",
                clean_reason="Creator already existed in unified table." if existed else "Creator accepted into candidate pool.",
                rule_key="creator_id_dedup" if existed else rule_key,
            )
            filtered.append(row)
            continue

        _record_creator_observation(
            storage,
            row=row,
            clean_status="filtered",
            clean_reason=filter_reason,
            rule_key=rule_key,
        )
        removed.append((name, filter_reason, videos[0][:40]))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    runtime_paths.ensure_runtime_layout()
    output_file = runtime_paths.get_input_dir() / f"openclaw_creators_filtered_{timestamp}.csv"

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)

    print("过滤完成")
    print(f"输出文件: {output_file}")
    print(f"保留博主: {len(filtered)} 个")
    print(f"移除博主: {len(removed)} 个")
    if removed:
        print("\n被移除的博主：")
        for name, reason, video in removed:
            print(f"  - {name:<22} [{reason}]  {video}")


if __name__ == "__main__":
    runtime_paths.ensure_runtime_layout()
    runtime_paths.seed_openclaw_csv_from_legacy()
    filter_creators(_parse_args())
